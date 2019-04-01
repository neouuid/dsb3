import lung_segmentation
import data_transforms
import data_iterators
import pathfinder
import utils
import string
import numpy as np
import lasagne as nn
import os
import utils_lung
# TODO: IMPORT A CORRECT PATCH MODEL HERE
import configs_seg_patch.luna_p8a1 as patch_config

# check if some predictions were generated
predictions_dir = utils.get_dir_path('model-predictions', pathfinder.METADATA_PATH)
outputs_path = predictions_dir + '/dsb_s2_p8a1_ls_elias'  # TODO write it here correctly
exclude_pids = []
if os.path.isdir(outputs_path):
    exclude_pids = os.listdir(outputs_path)
    exclude_pids = [utils_lung.extract_pid_filename(p) for p in exclude_pids]
#exclude_pids.append('b8bb02d229361a623a4dc57aa0e5c485')  # TODO hack here!

# calculate the following things correctly!
p_transform = {'patch_size': (416, 416, 416),
               'mm_patch_size': (416, 416, 416),
               'pixel_spacing': patch_config.p_transform['pixel_spacing']
               }
window_size = 160
stride = 128
n_windows = (p_transform['patch_size'][0] - window_size) / stride + 1


def data_prep_function(data, pixel_spacing, p_transform=p_transform):
    # TODO: MAKE SURE THAT DATA IS PREPROCESSED THE SAME WAY
    lung_mask = lung_segmentation.segment_HU_scan_elias(data)
    x, tf_matrix, lung_mask_out = data_transforms.transform_scan3d(data=data,
                                                                   pixel_spacing=pixel_spacing,
                                                                   p_transform=p_transform,
                                                                   lung_mask=lung_mask,
                                                                   p_transform_augment=None)
    x = data_transforms.pixelnormHU(x)
    return x, lung_mask_out, tf_matrix


print('pathfinder.DATA_PATH', pathfinder.DATA_PATH)
data_iterator = data_iterators.DSBScanLungMaskDataGenerator(data_path=pathfinder.DATA_PATH,
                                                            transform_params=p_transform,
                                                            data_prep_fun=data_prep_function,
                                                            exclude_pids=exclude_pids)


def build_model():
    metadata_dir = utils.get_dir_path('models', pathfinder.METADATA_PATH)
    metadata_path = utils.find_model_metadata(metadata_dir, patch_config.__name__.split('.')[-1])
    metadata = utils.load_pkl(metadata_path)

    print('Build model')
    model = patch_config.build_model(patch_size=(window_size, window_size, window_size))
    all_layers = nn.layers.get_all_layers(model.l_out)
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
    return model
