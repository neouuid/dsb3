import pickle
import string
import sys
import time
import lasagne as nn
import numpy as np
import theano
from datetime import datetime, timedelta
from collections import defaultdict
import utils
import logger
import theano.tensor as T
import buffering
from configuration import config, set_configuration
import pathfinder

theano.config.warn_float64 = 'raise'

if len(sys.argv) < 2:
    sys.exit("Usage: train.py <configuration_name>")

config_name = sys.argv[1]
set_configuration('configs_luna_props_patch', config_name)
expid = utils.generate_expid(config_name)
print()
print("Experiment ID: %s" % expid)
print()

# metadata
metadata_dir = utils.get_dir_path('models', pathfinder.METADATA_PATH)
metadata_path = metadata_dir + '/%s.pkl' % expid

# logs
logs_dir = utils.get_dir_path('logs', pathfinder.METADATA_PATH)
sys.stdout = logger.Logger(logs_dir + '/%s.log' % expid)
sys.stderr = sys.stdout

print('Build model')
model = config().build_model()
all_layers = nn.layers.get_all_layers(model.l_out)
all_params = nn.layers.get_all_params(model.l_out)
num_params = nn.layers.count_params(model.l_out)
print('  number of parameters: %d' % num_params)
print(string.ljust('  layer output shapes:', 36),)
print(string.ljust('#params:', 10),)
print('output shape:')
for layer in all_layers:
    name = string.ljust(layer.__class__.__name__, 32)
    num_param = sum([np.prod(p.get_value().shape) for p in layer.get_params()])
    num_param = string.ljust(num_param.__str__(), 10)
    print('    %s %s %s %s' % (name, num_param, layer.output_shape, layer.name))

train_loss = config().build_objective(model, deterministic=False)
valid_loss = config().build_objective(model, deterministic=True)

learning_rate_schedule = config().learning_rate_schedule
learning_rate = theano.shared(np.float32(learning_rate_schedule[0]))
updates = config().build_updates(train_loss, model, learning_rate)

x_shared = nn.utils.shared_empty(dim=len(model.l_in.shape))
y_shared = nn.utils.shared_empty(dim=len(model.l_target.shape))
if config().need_enable:
    z_shared = nn.utils.shared_empty(dim=len(model.l_enable_target.shape))

idx = T.lscalar('idx')
givens_train = {}
givens_train[model.l_in.input_var] = x_shared[idx * config().batch_size:(idx + 1) * config().batch_size]
givens_train[model.l_target.input_var] = y_shared[idx * config().batch_size:(idx + 1) * config().batch_size]
if config().need_enable:
    givens_train[model.l_enable_target.input_var] =  z_shared[idx * config().batch_size:(idx + 1) * config().batch_size]

givens_valid = {}
givens_valid[model.l_in.input_var] = x_shared
givens_valid[model.l_target.input_var] = y_shared
# at this moment we do not use the enable target
if config().need_enable:
    givens_valid[model.l_enable_target.input_var] = z_shared


#first make ordered list of objective functions
train_objectives = [config().d_objectives[obj_name] for obj_name in config().order_objectives]
test_objectives = [config().d_objectives_deterministic[obj_name] for obj_name in config().order_objectives]
# theano functions
print(givens_train)
iter_train = theano.function([idx], train_objectives, givens=givens_train, updates=updates)

print('test_objectives')
print(config().d_objectives_deterministic)
print('givens_valid')
print(givens_valid)
iter_validate = theano.function([], test_objectives, givens=givens_valid)

if config().restart_from_save:
    print('Load model parameters for resuming')
    resume_metadata = utils.load_pkl(config().restart_from_save)
    nn.layers.set_all_param_values(model.l_out, resume_metadata['param_values'])
    start_chunk_idx = resume_metadata['chunks_since_start'] + 1
    chunk_idxs = range(start_chunk_idx, config().max_nchunks)

    lr = np.float32(utils.current_learning_rate(learning_rate_schedule, start_chunk_idx))
    print('  setting learning rate to %.7f' % lr)
    learning_rate.set_value(lr)
    losses_eval_train = resume_metadata['losses_eval_train']
    losses_eval_valid = resume_metadata['losses_eval_valid']
else:
    chunk_idxs = range(config().max_nchunks)
    losses_eval_train = defaultdict(list)
    losses_eval_valid = defaultdict(list)
    start_chunk_idx = 0

train_data_iterator = config().train_data_iterator
valid_data_iterator = config().valid_data_iterator

print()
print('Data')
print('n train: %d' % train_data_iterator.nsamples)
print('n validation: %d' % valid_data_iterator.nsamples)
print('n chunks per epoch', config().nchunks_per_epoch)

print()
print('Train model')
chunk_idx = 0
start_time = time.time()
prev_time = start_time

tmp_losses_train = defaultdict(list)
losses_train_print = defaultdict(list)

# use buffering.buffered_gen_threaded()
for chunk_idx, (x_chunk_train, y_chunk_train, z_chunk_train, id_train) in zip(chunk_idxs, buffering.buffered_gen_threaded(
        train_data_iterator.generate())):
    if chunk_idx in learning_rate_schedule:
        lr = np.float32(learning_rate_schedule[chunk_idx])
        print('  setting learning rate to %.7f' % lr)
        print()
        learning_rate.set_value(lr)

    # load chunk to GPU
    x_shared.set_value(x_chunk_train)
    y_shared.set_value(y_chunk_train)
    if config().need_enable:
        z_shared.set_value(z_chunk_train)

    # make nbatches_chunk iterations
    for b in range(config().nbatches_chunk):
        losses = iter_train(b)
        # print(loss)
        for obj_idx, obj_name in enumerate(config().order_objectives):
            tmp_losses_train[obj_name].append(losses[obj_idx])
            losses_train_print[obj_name].append(losses[obj_idx])

    if (chunk_idx + 1) % 10 == 0:
        means = []
        for obj_idx, obj_name in enumerate(config().order_objectives):
            mean = np.mean(losses_train_print[obj_name])
            means.append(mean)
            print(obj_name, mean)
        print('Chunk %d/%d' % (chunk_idx + 1, config().max_nchunks), sum(means))
        
        losses_train_print = defaultdict(list)

    if ((chunk_idx + 1) % config().validate_every) == 0:
        # calculate mean train loss since the last validation phase
        means = []
        print('Mean train losses:')
        for obj_idx, obj_name in enumerate(config().order_objectives):
            train_mean = np.mean(tmp_losses_train[obj_name])
            losses_eval_train[obj_name] = train_mean
            means.append(train_mean)
            print(obj_name, train_mean)
        tmp_losses_train = defaultdict(list)
        print('Sum of train losses:', sum(means))
        print('Chunk %d/%d' % (chunk_idx + 1, config().max_nchunks), sum(means))

        # load validation data to GPU
        tmp_losses_valid = defaultdict(list)
        for i, (x_chunk_valid, y_chunk_valid, z_chunk_valid, ids_batch) in enumerate(
                buffering.buffered_gen_threaded(valid_data_iterator.generate(),
                                                buffer_size=2)):
            x_shared.set_value(x_chunk_valid)
            y_shared.set_value(y_chunk_valid)
            if config().need_enable:
                z_shared.set_value(z_chunk_valid)
            losses_valid = iter_validate()
            print(i, losses_valid[0], np.sum(losses_valid))
            for obj_idx, obj_name in enumerate(config().order_objectives):
                if z_chunk_valid[0, obj_idx]>0.5:
                    tmp_losses_valid[obj_name].append(losses_valid[obj_idx])


        # calculate validation loss across validation set
        means = [] 
        for obj_idx, obj_name in enumerate(config().order_objectives):
            valid_mean = np.mean(tmp_losses_valid[obj_name])
            losses_eval_valid[obj_name] = valid_mean
            means.append(valid_mean)
            print(obj_name, valid_mean)
        print('Sum of mean losses:', sum(means))


        now = time.time()
        time_since_start = now - start_time
        time_since_prev = now - prev_time
        prev_time = now
        est_time_left = time_since_start * (config().max_nchunks - chunk_idx + 1.) / (chunk_idx + 1. - start_chunk_idx)
        eta = datetime.now() + timedelta(seconds=est_time_left)
        eta_str = eta.strftime("%c")
        print("  %s since start (%.2f s)" % (utils.hms(time_since_start), time_since_prev))
        print("  estimated %s to go (ETA: %s)" % (utils.hms(est_time_left), eta_str))
        print()

    if ((chunk_idx + 1) % config().save_every) == 0:
        print()
        print('Chunk %d/%d' % (chunk_idx + 1, config().max_nchunks))
        print('Saving metadata, parameters')

        with open(metadata_path, 'w') as f:
            pickle.dump({
                'configuration_file': config_name,
                'git_revision_hash': utils.get_git_revision_hash(),
                'experiment_id': expid,
                'chunks_since_start': chunk_idx,
                'losses_eval_train': losses_eval_train,
                'losses_eval_valid': losses_eval_valid,
                'param_values': nn.layers.get_all_param_values(model.l_out)
            }, f, pickle.HIGHEST_PROTOCOL)
            print('  saved to %s' % metadata_path)
            print()
