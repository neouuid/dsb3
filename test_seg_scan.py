import sys
import lasagne as nn
import numpy as np
import theano
import pathfinder
import utils
from configuration import config, set_configuration
from utils_plots import plot_slice_3d_4
import theano.tensor as T
import blobs_detection
import logger
import time
import multiprocessing as mp
import buffering


def extract_candidates(predictions_scan, annotations, tf_matrix, pid, outputs_path):
    print('computing blobs')
    start_time = time.time()
    blobs = blobs_detection.blob_dog(predictions_scan[0, 0], min_sigma=1, max_sigma=15, threshold=0.1)
    print('blobs computation time:', (time.time() - start_time) / 60.)

    print('n_blobs detected', len(blobs))
    correct_blobs_idxs = []
    for zyxd in annotations:
        r = zyxd[-1] / 2.
        distance2 = ((zyxd[0] - blobs[:, 0]) ** 2
                     + (zyxd[1] - blobs[:, 1]) ** 2
                     + (zyxd[2] - blobs[:, 2]) ** 2)
        blob_idx = np.argmin(distance2)
        print('node', zyxd)
        print('closest blob', blobs[blob_idx])
        if distance2[blob_idx] <= r ** 2:
            correct_blobs_idxs.append(blob_idx)
        else:
            print('not detected !!!')

    # we will save blobs the the voxel space of the original image
    # blobs that are true detections will have blobs[-1] = 1 else 0
    blobs_original_voxel_coords = []
    for j in range(blobs.shape[0]):
        blob_j = np.append(blobs[j, :3], [1])
        blob_j_original = tf_matrix.dot(blob_j)
        blob_j_original[-1] = 1 if j in correct_blobs_idxs else 0
        if j in correct_blobs_idxs:
            print('blob in original', blob_j_original)
        blobs_original_voxel_coords.append(blob_j_original)

    blobs = np.asarray(blobs_original_voxel_coords)
    utils.save_pkl(blobs, outputs_path + '/%s.pkl' % pid)


jobs = []
theano.config.warn_float64 = 'raise'

if len(sys.argv) < 2:
    sys.exit("Usage: test_luna_scan.py <configuration_name>")

config_name = sys.argv[1]
set_configuration('configs_seg_scan', config_name)

# predictions path
predictions_dir = utils.get_dir_path('model-predictions', pathfinder.METADATA_PATH)
outputs_path = predictions_dir + '/%s' % config_name
utils.auto_make_dir(outputs_path)

# logs
logs_dir = utils.get_dir_path('logs', pathfinder.METADATA_PATH)
sys.stdout = logger.Logger(logs_dir + '/%s.log' % config_name)
sys.stderr = sys.stdout

# builds model and sets its parameters
model = config().build_model()

x_shared = nn.utils.shared_empty(dim=len(model.l_in.shape))
idx_z = T.lscalar('idx_z')
idx_y = T.lscalar('idx_y')
idx_x = T.lscalar('idx_x')

window_size = config().window_size
stride = config().stride
n_windows = config().n_windows

givens = {}
givens[model.l_in.input_var] = x_shared

get_predictions_patch = theano.function([],
                                        nn.layers.get_output(model.l_out, deterministic=True),
                                        givens=givens,
                                        on_unused_input='ignore')

valid_data_iterator = config().valid_data_iterator

print()
print('Data')
print('n samples: %d' % valid_data_iterator.nsamples)

start_time = time.time()
for n, (x, y, lung_mask, annotations, tf_matrix, pid) in enumerate(
        buffering.buffered_gen_threaded(valid_data_iterator.generate(), buffer_size=2)):
    print('-------------------------------------')
    print(n, pid)

    predictions_scan = np.zeros((1, 1, n_windows * stride, n_windows * stride, n_windows * stride))

    for iz in range(n_windows):
        for iy in range(n_windows):
            for ix in range(n_windows):
                start_time_patch = time.time()
                x_shared.set_value(x[:, :, iz * stride:(iz * stride) + window_size,
                                   iy * stride:(iy * stride) + window_size,
                                   ix * stride:(ix * stride) + window_size])
                predictions_patch = get_predictions_patch()

                predictions_scan[0, 0,
                iz * stride:(iz + 1) * stride,
                iy * stride:(iy + 1) * stride,
                ix * stride:(ix + 1) * stride] = predictions_patch

    if predictions_scan.shape != x.shape:
        pad_width = (np.asarray(x.shape) - np.asarray(predictions_scan.shape)) / 2
        pad_width = [(p, p) for p in pad_width]
        predictions_scan = np.pad(predictions_scan, pad_width=pad_width, mode='constant')

    if lung_mask is not None:
        predictions_scan *= lung_mask

    for nodule_n, zyxd in enumerate(annotations):
        plot_slice_3d_4(input=x[0, 0], mask=y[0, 0], prediction=predictions_scan[0, 0],
                        lung_mask=lung_mask[0, 0] if lung_mask is not None else x[0, 0],
                        axis=0, pid='-'.join([str(n), str(nodule_n), str(pid)]),
                        img_dir=outputs_path, idx=zyxd)
    print('saved plot')
    print('time since start:', (time.time() - start_time) / 60.)

    jobs = [job for job in jobs if job.is_alive]
    if len(jobs) >= 3:
        jobs[0].join()
        del jobs[0]
    jobs.append(
        mp.Process(target=extract_candidates, args=(predictions_scan, annotations, tf_matrix, pid, outputs_path)))
    jobs[-1].daemon = True
    jobs[-1].start()

for job in jobs: job.join()
