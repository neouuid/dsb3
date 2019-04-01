import string
import sys
import lasagne as nn
import numpy as np
import theano
import buffering
import pathfinder
import utils
from configuration import config, set_configuration
from utils_plots import plot_slice_3d_3
import utils_lung
import logger

theano.config.warn_float64 = 'raise'

if len(sys.argv) < 2:
    sys.exit("Usage: train.py <configuration_name>")

config_name = sys.argv[1]
set_configuration('configs_seg_patch', config_name)

# metadata
metadata_dir = utils.get_dir_path('models', pathfinder.METADATA_PATH)
metadata_path = utils.find_model_metadata(metadata_dir, config_name)

metadata = utils.load_pkl(metadata_path)
expid = metadata['experiment_id']

# logs
logs_dir = utils.get_dir_path('logs', pathfinder.METADATA_PATH)
sys.stdout = logger.Logger(logs_dir + '/%s-test.log' % expid)
sys.stderr = sys.stdout

# predictions path
predictions_dir = utils.get_dir_path('model-predictions', pathfinder.METADATA_PATH)
outputs_path = predictions_dir + '/' + expid
utils.auto_make_dir(outputs_path)

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
    print('    %s %s %s' % (name, num_param, layer.output_shape))

nn.layers.set_all_param_values(model.l_out, metadata['param_values'])

valid_loss = config().build_objective(model, deterministic=True)

x_shared = nn.utils.shared_empty(dim=len(model.l_in.shape))

givens_valid = {}
givens_valid[model.l_in.input_var] = x_shared

# theano functions
iter_get_predictions = theano.function([], nn.layers.get_output(model.l_out, deterministic=True), givens=givens_valid)
valid_data_iterator = config().valid_data_iterator

print()
print('Data')
print('n validation: %d' % valid_data_iterator.nsamples)

valid_losses_dice = []
tp = 0
for n, (x_chunk, y_chunk, id_chunk) in enumerate(buffering.buffered_gen_threaded(valid_data_iterator.generate())):
    # load chunk to GPU
    x_shared.set_value(x_chunk)
    predictions = iter_get_predictions()
    targets = y_chunk
    inputs = x_chunk

    if predictions.shape != targets.shape:
        pad_width = (np.asarray(targets.shape) - np.asarray(predictions.shape)) / 2
        pad_width = [(p, p) for p in pad_width]
        predictions = np.pad(predictions, pad_width=pad_width, mode='constant')

    dice = utils_lung.dice_index(predictions, targets)
    print(n, id_chunk, dice)
    valid_losses_dice.append(dice)
    if np.sum(predictions * targets) / np.sum(targets) > 0.1:
        tp += 1
    else:
        print('not detected!!!!')

    for k in range(predictions.shape[0]):
        plot_slice_3d_3(input=inputs[k, 0], mask=targets[k, 0], prediction=predictions[k, 0],
                        axis=0, pid='-'.join([str(n), str(k), str(id_chunk[k])]),
                        img_dir=outputs_path)

print('Dice index validation loss', np.mean(valid_losses_dice))
print('TP', tp)
