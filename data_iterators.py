import numpy as np
import utils_lung
import pathfinder
import utils


# 6% to 28% for nodules 5 to 10 mm,
prob5 = (0.01+0.06)/2.
slope10 = (0.28-prob5) / (10.-5.)
offset10 = prob5 - slope10*5.

slope20 = (0.64-0.28) / (20.-10.)
offset20 = 0.28 - slope20*10.

# and 64% to 82% for nodules >20 mm in diameter
slope25 = (0.82-0.64) / (25.-20.)
offset25 = 0.64 - slope25*20.

slope30 = (0.93-0.82) / (30.-25.)
offset30 = 0.82 - slope30*25.

# For nodules more than 3 cm in diameter, 93% to 97% are malignant
slope40 = (0.97-0.93) / (40.-30.)
offset40 = 0.93 - slope40*30.

def diameter_to_prob(diam):
    # The prevalence of malignancy is 0% to 1% for nodules <5 mm,
    if diam < 5:
        p = prob5*diam/5.
    elif diam < 10:
        p = slope10*diam+offset10
    elif diam < 20:
        p = slope20*diam+offset20
    elif diam < 25:
        p = slope25*diam+offset25
    elif diam < 30:
        p = slope30*diam+offset30
    else:
        p = slope40 * diam + offset40
    return np.clip(p ,0.,1.)


class LunaDataGenerator(object):
    def __init__(self, data_path, transform_params, data_prep_fun, rng,
                 random, infinite, patient_ids=None, **kwargs):

        self.patient_ids = patient_ids
        if patient_ids:
            self.patient_paths = [data_path + '/' + p + '.mhd' for p in patient_ids]
        else:
            patient_paths = utils_lung.get_patient_data_paths(data_path)
            self.patient_paths = [p for p in patient_paths if '.mhd' in p]

        self.id2annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)
        self.nsamples = len(self.patient_paths)
        self.data_path = data_path
        self.rng = rng
        self.random = random
        self.infinite = infinite
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs)):
                idx = rand_idxs[pos]

                patient_path = self.patient_paths[idx]
                pid = utils_lung.extract_pid_filename(patient_path)

                img, origin, pixel_spacing = utils_lung.read_mhd(patient_path)
                x, y, annotations, tf_matrix = self.data_prep_fun(data=img,
                                                                  pixel_spacing=pixel_spacing,
                                                                  luna_annotations=
                                                                  self.id2annotations[pid],
                                                                  luna_origin=origin)

                x = np.float32(x)[None, None, :, :, :]
                y = np.float32(y)[None, None, :, :, :]

                yield x, y, None, annotations, tf_matrix, pid

            if not self.infinite:
                break



class LunaSimpleDataGenerator(object):
    def __init__(self, data_path, patient_ids=None, **kwargs):

        self.patient_ids = patient_ids

        self.data_path = data_path
        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'

        if patient_ids:
            self.patient_paths = [data_path + '/' + p + self.file_extension for p in patient_ids]
        else:
            patient_paths = utils_lung.get_patient_data_paths(data_path)
            self.patient_paths = [p for p in patient_paths if self.file_extension in p]
        
        self.nsamples = len(self.patient_paths)

        print(self.data_path)

    def generate(self):
        for patient_path in self.patient_paths:
            pid = utils_lung.extract_pid_filename(patient_path)

            img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)

            x = np.float32(img)

            yield x, pid




class LunaScanPositiveDataGenerator(LunaDataGenerator):
    def __init__(self, data_path, transform_params, data_prep_fun, rng,
                 random, infinite, patient_ids=None, **kwargs):
        super(LunaScanPositiveDataGenerator, self).__init__(data_path, transform_params, data_prep_fun, rng,
                                                            random, infinite, patient_ids, **kwargs)
        patient_ids_all = [utils_lung.extract_pid_filename(p) for p in self.patient_paths]
        patient_ids_pos = [pid for pid in patient_ids_all if pid in self.id2annotations.keys()]
        self.patient_paths = [data_path + '/' + p + '.mhd' for p in patient_ids_pos]
        self.nsamples = len(self.patient_paths)


class LunaScanPositiveLungMaskDataGenerator(LunaDataGenerator):
    def __init__(self, data_path, batch_size, transform_params, data_prep_fun, rng,
                 full_batch, random, infinite, patient_ids=None, **kwargs):
        super(LunaScanPositiveLungMaskDataGenerator, self).__init__(data_path, transform_params,
                                                                    data_prep_fun, rng,
                                                                    random, infinite, patient_ids, **kwargs)

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs)):
                idx = rand_idxs[pos]

                patient_path = self.patient_paths[idx]
                pid = utils_lung.extract_pid_filename(patient_path)

                img, origin, pixel_spacing = utils_lung.read_mhd(patient_path)
                x, y, lung_mask, annotations, tf_matrix = self.data_prep_fun(data=img,
                                                                             pixel_spacing=pixel_spacing,
                                                                             luna_annotations=
                                                                             self.id2annotations[pid],
                                                                             luna_origin=origin)

                x = np.float32(x)[None, None, :, :, :]
                y = np.float32(y)[None, None, :, :, :]
                lung_mask = np.float32(lung_mask)[None, None, :, :, :]

                yield x, y, lung_mask, annotations, tf_matrix, pid

            if not self.infinite:
                break



class LunaScanMaskPositiveDataGenerator(LunaDataGenerator):
    def __init__(self, data_path, seg_data_path, batch_size, transform_params, data_prep_fun, rng,
                 full_batch, random, infinite, patient_ids=None, **kwargs):
        super(LunaScanMaskPositiveDataGenerator, self).__init__(data_path, transform_params,
                                                                    data_prep_fun, rng,
                                                                    random, infinite, patient_ids, **kwargs)
        self.seg_data_path = seg_data_path
        self.mask_paths = [seg_data_path + '/' + p + '.mhd' for p in self.patient_ids]

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs)):
                idx = rand_idxs[pos]

                ct_scan_path = self.patient_paths[idx]
                mask_path = self.mask_paths[idx]

                pid = utils_lung.extract_pid_filename(ct_scan_path)

                ct_scan, ct_origin, ct_pixel_spacing = utils_lung.read_mhd(ct_scan_path)
                mask, mask_origin, mask_pixel_spacing = utils_lung.read_mhd(mask_path)

                assert(sum(abs(ct_origin-mask_origin)) < 1e-9)
                assert(sum(abs(ct_pixel_spacing-mask_pixel_spacing)) < 1e-9)

                ct, lung_mask, annotations, tf_matrix = self.data_prep_fun(ct_scan=ct_scan, mask=mask,
                                                                             pixel_spacing=ct_pixel_spacing,
                                                                             luna_annotations=
                                                                             self.id2annotations[pid],
                                                                             luna_origin=ct_origin)

                ct = np.float32(ct)[None, None, :, :, :]
                lung_mask = np.float32(lung_mask)[None, None, :, :, :]

                yield ct, lung_mask, annotations, tf_matrix, pid

            if not self.infinite:
                break


#for lung segmentation, does not work yet
class PatchLunaDataGenerator(object):
    def __init__(self, ct_data_path, seg_data_path, batch_size, transform_params, data_prep_fun, rng,
                 full_batch, random, infinite, patient_ids=None, **kwargs):

        if patient_ids:
            self.patient_ids = patient_ids
            #self.patient_paths = [data_path + '/' + p + '.mhd' for p in patient_ids]
        else:
            patient_paths = utils_lung.get_patient_data_paths(ct_data_path)
            #self.patient_paths = [p for p in patient_paths if '.mhd' in p]
            self.patient_ids = [utils_lung.extract_pid_filename(p) for p in self.patient_paths]\

        self.nsamples = len(self.patient_ids)
        self.ct_data_path = ct_data_path
        self.seg_data_path = seg_data_path
        self.rng = rng
        self.random = random
        self.infinite = infinite
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.batch_size = batch_size
        self.full_batch = full_batch

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]
                nb = len(idxs_batch)
                # allocate batches
                x_batch = np.zeros((nb, 1) + self.transform_params['patch_size'], dtype='float32')
                y_batch = np.zeros((nb, 1) + self.transform_params['patch_size'], dtype='float32')
                patients_ids = []

                for i, idx in enumerate(idxs_batch):
                    pid = self.patient_ids[idx]
                    ct_path = self.ct_data_path + pid + '.mhd'
                    seg_path = self.seg_data_path + pid + '.mhd'
                    patients_ids.append(pid)

                    ct_img, ct_origin, ct_pixel_spacing = utils_lung.read_mhd(ct_path)
                    seg_img, seg_origin, seg_pixel_spacing = utils_lung.read_mhd(seg_path)

                    assert(np.sum(ct_origin-seg_origin) <  1e-9)
                    assert(np.sum(ct_pixel_spacing-seg_pixel_spacing) <  1e-9)

                    print('ct_img.shape', ct_img.shape)
                    print('seg_img.shape', seg_img.shape)
                    w,h,d = self.transform_params['patch_size']
                    patch_center = [self.rng.randint(w/2, ct_img.shape[0]-w/2),
                                    self.rng.randint(h/2, ct_img.shape[1]-h/2),
                                    self.rng.randint(d/2, ct_img.shape[1]-d/2)]
                    print(patch_center)


                    x_batch[i, 0, :, :, :], y_batch[i, 0, :, :, :]  = self.data_prep_fun(ct_img=ct_img, seg_img=seg_img,
                                                                    patch_center=patch_center,
                                                                    pixel_spacing=ct_pixel_spacing,
                                                                    luna_origin=ct_origin)

                    # y_batch[i, 0, :, :, :],  = self.data_prep_fun(data=seg_img,
                    #                                                 patch_center=patch_center,
                    #                                                 pixel_spacing=seg_pixel_spacing,
                    #                                                 luna_origin=seg_origin)
                if self.full_batch:
                    if nb == self.batch_size:
                        yield x_batch, y_batch, patients_ids
                else:
                    yield x_batch, y_batch, patients_ids

            if not self.infinite:
                break

#works, tested
class LunaScanDataGenerator(object):
    def __init__(self, ct_data_path, seg_data_path, patient_ids=None, **kwargs):

        if patient_ids:
            self.patient_ids = patient_ids
            #self.patient_paths = [data_path + '/' + p + '.mhd' for p in patient_ids]
        else:
            patient_paths = utils_lung.get_patient_data_paths(ct_data_path)
            #self.patient_paths = [p for p in patient_paths if '.mhd' in p]
            self.patient_ids = [utils_lung.extract_pid_filename(p) for p in self.patient_paths]\

        self.nsamples = len(self.patient_ids)
        self.ct_data_path = ct_data_path
        self.seg_data_path = seg_data_path
        

    def generate(self):
        for pid in self.patient_ids:
            ct_path = self.ct_data_path + pid + '.mhd'
            seg_path = self.seg_data_path + pid + '.mhd'

            ct_img, ct_origin, ct_pixel_spacing = utils_lung.read_mhd(ct_path)
            seg_img, seg_origin, seg_pixel_spacing = utils_lung.read_mhd(seg_path)

            assert(np.sum(ct_origin-seg_origin) <  1e-9)
            assert(np.sum(ct_pixel_spacing-seg_pixel_spacing) <  1e-9)

            print('ct_img.shape', ct_img.shape)
            print('seg_img.shape', seg_img.shape)

            yield ct_img, seg_img, pid


class PatchPositiveLunaDataGenerator(object):
    def __init__(self, data_path, batch_size, transform_params, data_prep_fun, rng,
                 full_batch, random, infinite, patient_ids=None, **kwargs):

        self.id2annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)

        if patient_ids:
            self.patient_paths = [data_path + '/' + p + '.mhd' for p in patient_ids]
        else:
            patient_paths = utils_lung.get_patient_data_paths(data_path)
            self.patient_paths = [p for p in patient_paths if '.mhd' in p]

        patient_ids_all = [utils_lung.extract_pid_filename(p) for p in self.patient_paths]
        patient_ids_pos = [pid for pid in patient_ids_all if pid in self.id2annotations.keys()]
        self.patient_paths = [data_path + '/' + p + '.mhd' for p in patient_ids_pos]

        self.nsamples = len(self.patient_paths)
        self.data_path = data_path
        self.rng = rng
        self.random = random
        self.infinite = infinite
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.batch_size = batch_size
        self.full_batch = full_batch

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]
                nb = len(idxs_batch)
                # allocate batches
                x_batch = np.zeros((nb, 1) + self.transform_params['patch_size'], dtype='float32')
                y_batch = np.zeros((nb, 1) + self.transform_params['patch_size'], dtype='float32')
                patients_ids = []

                for i, idx in enumerate(idxs_batch):
                    patient_path = self.patient_paths[idx]
                    id = utils_lung.extract_pid_filename(patient_path)
                    patients_ids.append(id)
                    img, origin, pixel_spacing = utils_lung.read_mhd(patient_path)

                    patient_annotations = self.id2annotations[id]
                    patch_center = patient_annotations[self.rng.randint(len(patient_annotations))]
                    x_batch[i, 0, :, :, :], y_batch[i, 0, :, :, :] = self.data_prep_fun(data=img,
                                                                                        patch_center=patch_center,
                                                                                        pixel_spacing=pixel_spacing,
                                                                                        luna_annotations=patient_annotations,
                                                                                        luna_origin=origin)
                if self.full_batch:
                    if nb == self.batch_size:
                        yield x_batch, y_batch, patients_ids
                else:
                    yield x_batch, y_batch, patients_ids

            if not self.infinite:
                break



class ValidPatchPositiveLunaDataGenerator(object):
    def __init__(self, data_path, transform_params, patient_ids, data_prep_fun, **kwargs):

        id2positive_annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)

        self.id2positive_annotations = {}
        self.id2patient_path = {}
        n_positive = 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                n_pos = len(id2positive_annotations[pid])
                self.id2patient_path[pid] = data_path + '/' + pid + '.mhd'
                n_positive += n_pos

        self.nsamples = n_positive
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params

    def generate(self):

        for pid in self.id2positive_annotations.iterkeys():
            for patch_center in self.id2positive_annotations[pid]:
                patient_path = self.id2patient_path[pid]
                img, origin, pixel_spacing = utils_lung.read_mhd(patient_path)

                patient_annotations = self.id2positive_annotations[pid]
                x_batch, y_batch = self.data_prep_fun(data=img,
                                                      patch_center=patch_center,
                                                      pixel_spacing=pixel_spacing,
                                                      luna_annotations=patient_annotations,
                                                      luna_origin=origin)
                x_batch = np.float32(x_batch)[None, None, :, :, :]
                y_batch = np.float32(y_batch)[None, None, :, :, :]
                yield x_batch, y_batch, [pid]


class CandidatesLunaDataGenerator(object):
    def __init__(self, data_path, batch_size, transform_params, patient_ids, data_prep_fun, rng,
                 full_batch, random, infinite, positive_proportion, **kwargs):

        id2positive_annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.patient_paths = []
        n_positive, n_negative = 0, 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                self.id2negative_annotations[pid] = id2negative_annotations[pid]
                self.patient_paths.append(data_path + '/' + pid + self.file_extension)
                n_positive += len(id2positive_annotations[pid])
                n_negative += len(id2negative_annotations[pid])

        print('n positive', n_positive)
        print('n negative', n_negative)

        self.nsamples = len(self.patient_paths)

        print('n patients', self.nsamples)
        self.data_path = data_path
        self.batch_size = batch_size
        self.rng = rng
        self.full_batch = full_batch
        self.random = random
        self.infinite = infinite
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.positive_proportion = positive_proportion

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]
                nb = len(idxs_batch)
                # allocate batches
                x_batch = np.zeros((nb, 1) + self.transform_params['patch_size'], dtype='float32')
                y_batch = np.zeros((nb, 1), dtype='float32')
                patients_ids = []

                for i, idx in enumerate(idxs_batch):
                    patient_path = self.patient_paths[idx]

                    id = utils_lung.extract_pid_filename(patient_path, self.file_extension)
                    patients_ids.append(id)

                    img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                        if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                    if i < np.rint(self.batch_size * self.positive_proportion):
                        patient_annotations = self.id2positive_annotations[id]
                    else:
                        patient_annotations = self.id2negative_annotations[id]

                    patch_center = patient_annotations[self.rng.randint(len(patient_annotations))]

                    y_batch[i] = float(patch_center[-1] > 0)
                    x_batch[i, 0, :, :, :] = self.data_prep_fun(data=img,
                                                                patch_center=patch_center,
                                                                pixel_spacing=pixel_spacing,
                                                                luna_origin=origin)

                if self.full_batch:
                    if nb == self.batch_size:
                        yield x_batch, y_batch, patients_ids
                else:
                    yield x_batch, y_batch, patients_ids

            if not self.infinite:
                break



class CandidatesLunaDataGenerator(object):
    def __init__(self, data_path, batch_size, transform_params, patient_ids, data_prep_fun, rng,
                 full_batch, random, infinite, positive_proportion, return_malignancy=False, **kwargs):

        id2positive_annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.patient_paths = []
        n_positive, n_negative = 0, 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                self.id2negative_annotations[pid] = id2negative_annotations[pid]
                self.patient_paths.append(data_path + '/' + pid + self.file_extension)
                n_positive += len(id2positive_annotations[pid])
                n_negative += len(id2negative_annotations[pid])

        print('n positive', n_positive)
        print('n negative', n_negative)

        self.nsamples = len(self.patient_paths)

        print('n patients', self.nsamples)
        self.data_path = data_path
        self.batch_size = batch_size
        self.rng = rng
        self.full_batch = full_batch
        self.random = random
        self.infinite = infinite
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.positive_proportion = positive_proportion
        self.return_malignancy = return_malignancy

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]
                nb = len(idxs_batch)
                # allocate batches
                x_batch = np.zeros((nb,) + self.transform_params['patch_size'], dtype='float32')
                y_batch = np.zeros((nb,), dtype='float32')
                patients_ids = []

                for i, idx in enumerate(idxs_batch):
                    patient_path = self.patient_paths[idx]

                    id = utils_lung.extract_pid_filename(patient_path, self.file_extension)
                    patients_ids.append(id)

                    img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                        if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                    if i < np.rint(self.batch_size * self.positive_proportion):
                        patient_annotations = self.id2positive_annotations[id]
                    else:
                        patient_annotations = self.id2negative_annotations[id]

                    patch_center = patient_annotations[self.rng.randint(len(patient_annotations))]

                    if self.return_malignancy:
                        y_batch[i] = np.float32(diameter_to_prob(patch_center[-1]))
                    else:
                        y_batch[i] = float(patch_center[-1] > 0) 
                    x_batch[i, :, :, :] = self.data_prep_fun(data=img,
                                                                patch_center=patch_center,
                                                                pixel_spacing=pixel_spacing,
                                                                luna_origin=origin)

                if self.full_batch:
                    if nb == self.batch_size:
                        yield x_batch, y_batch, patients_ids
                else:
                    yield x_batch, y_batch, patients_ids

            if not self.infinite:
                break


class CandidatesLunaValidDataGenerator(object):
    def __init__(self, data_path, transform_params, patient_ids, data_prep_fun, return_malignancy=False, **kwargs):
        rng = np.random.RandomState(42)  # do not change this!!!

        id2positive_annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.id2patient_path = {}
        n_positive, n_negative = 0, 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                negative_annotations = id2negative_annotations[pid]
                n_pos = len(id2positive_annotations[pid])
                n_neg = len(id2negative_annotations[pid])
                neg_idxs = rng.choice(n_neg, size=n_pos, replace=False)
                negative_annotations_selected = []
                for i in neg_idxs:
                    negative_annotations_selected.append(negative_annotations[i])
                self.id2negative_annotations[pid] = negative_annotations_selected

                self.id2patient_path[pid] = data_path + '/' + pid + self.file_extension
                n_positive += n_pos
                n_negative += n_pos

        print('n positive', n_positive)
        print('n negative', n_negative)

        self.nsamples = len(self.id2patient_path)
        self.data_path = data_path
        self.rng = rng
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.return_malignancy = return_malignancy

    def generate(self):

        for pid in self.id2positive_annotations.iterkeys():
            for patch_center in self.id2positive_annotations[pid]:
                patient_path = self.id2patient_path[pid]

                img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                    if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                
                if self.return_malignancy:
                    y_batch = np.array([diameter_to_prob(patch_center[-1])], dtype='float32')
                else:
                    y_batch = np.array([1.], dtype='float32')

                x_batch = np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, :, :, :]

                yield x_batch, y_batch, [pid]

            for patch_center in self.id2negative_annotations[pid]:
                patient_path = self.id2patient_path[pid]

                img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                    if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                y_batch = np.array([0.], dtype='float32')
                x_batch = np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, :, :, :]

                yield x_batch, y_batch, [pid]


class FixedCandidatesLunaDataGenerator(object):
    def __init__(self, data_path, transform_params, id2candidates_path, data_prep_fun, top_n=None):

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2candidates_path = id2candidates_path
        self.id2patient_path = {}
        for pid in id2candidates_path.keys():
            self.id2patient_path[pid] = data_path + '/' + pid + self.file_extension

        self.nsamples = len(self.id2patient_path)
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.top_n = top_n

    def generate(self):

        for pid in self.id2candidates_path.iterkeys():
            patient_path = self.id2patient_path[pid]
            print('PATIENT', pid)
            candidates = utils.load_pkl(self.id2candidates_path[pid])
            if self.top_n is not None:
                candidates = candidates[:self.top_n]
                print(candidates)
            print('n blobs', len(candidates))

            img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)

            for candidate in candidates:
                y_batch = np.array(candidate, dtype='float32')
                patch_center = candidate[:3]
                x_batch = np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, None, :, :, :]

                yield x_batch, y_batch, [pid]



class CandidatesLunaSizeDataGenerator(object):
    def __init__(self, data_path, batch_size, transform_params, patient_ids, data_prep_fun, rng,
                 full_batch, random, infinite, positive_proportion, **kwargs):

        id2positive_annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.patient_paths = []
        n_positive, n_negative = 0, 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                self.id2negative_annotations[pid] = id2negative_annotations[pid]
                self.patient_paths.append(data_path + '/' + pid + self.file_extension)
                n_positive += len(id2positive_annotations[pid])
                n_negative += len(id2negative_annotations[pid])

        print('n positive', n_positive)
        print('n negative', n_negative)

        self.nsamples = len(self.patient_paths)

        print('n patients', self.nsamples)
        self.data_path = data_path
        self.batch_size = batch_size
        self.rng = rng
        self.full_batch = full_batch
        self.random = random
        self.infinite = infinite
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.positive_proportion = positive_proportion

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]
                nb = len(idxs_batch)
                # allocate batches
                x_batch = np.zeros((nb, 1) + self.transform_params['patch_size'], dtype='float32')
                y_batch = np.zeros((nb, 1), dtype='float32')
                patients_ids = []

                for i, idx in enumerate(idxs_batch):
                    patient_path = self.patient_paths[idx]

                    id = utils_lung.extract_pid_filename(patient_path, self.file_extension)
                    patients_ids.append(id)

                    img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                        if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                    if i < np.rint(self.batch_size * self.positive_proportion):
                        patient_annotations = self.id2positive_annotations[id]
                    else:
                        patient_annotations = self.id2negative_annotations[id]

                    patch_center = patient_annotations[self.rng.randint(len(patient_annotations))]

                    y_batch[i] = float(patch_center[-1])
                    x_batch[i, 0, :, :, :] = self.data_prep_fun(data=img,
                                                                patch_center=patch_center,
                                                                pixel_spacing=pixel_spacing,
                                                                luna_origin=origin)

                if self.full_batch:
                    if nb == self.batch_size:
                        yield x_batch, y_batch, patients_ids
                else:
                    yield x_batch, y_batch, patients_ids

            if not self.infinite:
                break

class CandidatesLunaSizeValidDataGenerator(object):
    def __init__(self, data_path, transform_params, patient_ids, data_prep_fun, **kwargs):
        rng = np.random.RandomState(42)  # do not change this!!!

        id2positive_annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.id2patient_path = {}
        n_positive, n_negative = 0, 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                negative_annotations = id2negative_annotations[pid]
                n_pos = len(id2positive_annotations[pid])
                n_neg = len(id2negative_annotations[pid])
                neg_idxs = rng.choice(n_neg, size=n_pos, replace=False)
                negative_annotations_selected = []
                for i in neg_idxs:
                    negative_annotations_selected.append(negative_annotations[i])
                self.id2negative_annotations[pid] = negative_annotations_selected

                self.id2patient_path[pid] = data_path + '/' + pid + self.file_extension
                n_positive += n_pos
                n_negative += n_pos

        print('n positive', n_positive)
        print('n negative', n_negative)

        self.nsamples = len(self.id2patient_path)
        self.data_path = data_path
        self.rng = rng
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params

    def generate(self):

        for pid in self.id2positive_annotations.iterkeys():
            for patch_center in self.id2positive_annotations[pid]:
                patient_path = self.id2patient_path[pid]

                img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                    if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                y_batch = np.array([[float(patch_center[-1])]], dtype='float32')
                x_batch = np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, None, :, :, :]

                yield x_batch, y_batch, [pid]

            for patch_center in self.id2negative_annotations[pid]:
                patient_path = self.id2patient_path[pid]

                img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                    if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                y_batch = np.array([[0.]], dtype='float32')
                x_batch = np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, None, :, :, :]

                yield x_batch, y_batch, [pid]



class CandidatesLunaSizeBinDataGenerator(object):
    def __init__(self, data_path, batch_size, transform_params, patient_ids, data_prep_fun, rng,
                 full_batch, random, infinite, positive_proportion, bin_borders = [4,8,20,50], **kwargs):

        id2positive_annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.patient_paths = []
        n_positive, n_negative = 0, 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                self.id2negative_annotations[pid] = id2negative_annotations[pid]
                self.patient_paths.append(data_path + '/' + pid + self.file_extension)
                n_positive += len(id2positive_annotations[pid])
                n_negative += len(id2negative_annotations[pid])

        print('n positive', n_positive)
        print('n negative', n_negative)

        self.nsamples = len(self.patient_paths)

        print('n patients', self.nsamples)
        self.data_path = data_path
        self.batch_size = batch_size
        self.rng = rng
        self.full_batch = full_batch
        self.random = random
        self.infinite = infinite
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.positive_proportion = positive_proportion
        self.bin_borders = bin_borders

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]
                nb = len(idxs_batch)
                # allocate batches
                x_batch = np.zeros((nb,) + self.transform_params['patch_size'], dtype='float32')
                y_batch = np.zeros((nb,), dtype='float32')
                patients_ids = []

                for i, idx in enumerate(idxs_batch):
                    patient_path = self.patient_paths[idx]

                    id = utils_lung.extract_pid_filename(patient_path, self.file_extension)
                    patients_ids.append(id)

                    img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                        if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                    if i < np.rint(self.batch_size * self.positive_proportion):
                        patient_annotations = self.id2positive_annotations[id]
                    else:
                        patient_annotations = self.id2negative_annotations[id]

                    patch_center = patient_annotations[self.rng.randint(len(patient_annotations))]

                    diameter = patch_center[-1]
                    if diameter > 0.:
                        ybin = 0
                        for idx, border in enumerate(self.bin_borders):
                            if diameter<border:
                                ybin = idx
                                break                            
                        y_batch[i] = 1. + ybin
                    else:
                        y_batch[i] = 0. 
                    #print('y_batch[i]', y_batch[i], 'diameter', diameter)

                    x_batch[i, :, :, :] = self.data_prep_fun(data=img,
                                                                patch_center=patch_center,
                                                                pixel_spacing=pixel_spacing,
                                                                luna_origin=origin)

                if self.full_batch:
                    if nb == self.batch_size:
                        yield x_batch, y_batch, patients_ids
                else:
                    yield x_batch, y_batch, patients_ids

            if not self.infinite:
                break

class CandidatesLunaSizeBinValidDataGenerator(object):
    def __init__(self, data_path, transform_params, patient_ids, data_prep_fun, bin_borders = [4,8,20,50], **kwargs):
        rng = np.random.RandomState(42)  # do not change this!!!

        id2positive_annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.id2patient_path = {}
        n_positive, n_negative = 0, 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                negative_annotations = id2negative_annotations[pid]
                n_pos = len(id2positive_annotations[pid])
                n_neg = len(id2negative_annotations[pid])
                neg_idxs = rng.choice(n_neg, size=n_pos, replace=False)
                negative_annotations_selected = []
                for i in neg_idxs:
                    negative_annotations_selected.append(negative_annotations[i])
                self.id2negative_annotations[pid] = negative_annotations_selected

                self.id2patient_path[pid] = data_path + '/' + pid + self.file_extension
                n_positive += n_pos
                n_negative += n_pos

        print('n positive', n_positive)
        print('n negative', n_negative)

        self.nsamples = len(self.id2patient_path)
        self.data_path = data_path
        self.rng = rng
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.bin_borders = bin_borders

    def generate(self):

        for pid in self.id2positive_annotations.iterkeys():
            for patch_center in self.id2positive_annotations[pid]:
                patient_path = self.id2patient_path[pid]

                img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                    if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)

                diameter = patch_center[3]                        
                ybin = 0
                for idx, border in enumerate(self.bin_borders):
                    if diameter<border:
                        ybin = idx
                        break  

                y_batch = np.array([1. + ybin], dtype='float32')
                x_batch = np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, :, :, :]

                yield x_batch, y_batch, [pid]

            for patch_center in self.id2negative_annotations[pid]:
                patient_path = self.id2patient_path[pid]

                img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                    if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                y_batch = np.array([0.], dtype='float32')
                x_batch = np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, :, :, :]

                yield x_batch, y_batch, [pid]



class CandidatesLunaPropsDataGenerator(object):
    def __init__(self, data_path, batch_size, transform_params, patient_ids, data_prep_fun, rng,
                 full_batch, random, infinite, 
                 positive_proportion,
                 order_objectives,
                 property_type,
                 property_bin_borders = None,
                 return_enable_target_vector = False, **kwargs):

        id2positive_annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.all_pids = patient_ids
        self.pos_pids = []
        self.neg_pids = []
        n_positive, n_negative = 0, 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                self.id2negative_annotations[pid] = id2negative_annotations[pid]
                self.pos_pids.append(pid)
                n_positive += len(id2positive_annotations[pid])
                n_negative += len(id2negative_annotations[pid])
            elif pid in id2negative_annotations:
                self.id2negative_annotations[pid] = id2negative_annotations[pid]
                self.neg_pids.append(pid)
                n_negative += len(id2negative_annotations[pid])
            else:
                print('WARNING something weird happens')

        print('n positive', n_positive)
        print('n negative', n_negative)

        self.n_neg_cans = n_negative
        self.n_pos_cans = n_positive

        self.n_pos_pids = len(self.pos_pids)
        self.n_neg_pids = len(self.neg_pids)

        self.nsamples = len(self.all_pids)
        print('n patients', self.nsamples)
        self.data_path = data_path
        self.batch_size = batch_size
        self.rng = rng
        self.full_batch = full_batch
        self.random = random
        self.infinite = infinite
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.positive_proportion = positive_proportion

        self.order_objectives = order_objectives
        self.property_bin_borders = property_bin_borders
	self.property_type = property_type
        #self.return_enable_target_vector = return_enable_target_vector

    def L2(self, a,b):
        return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)**(0.5)

    def build_ground_truth_vector(self, pid, patch_center):
        properties={}
        feature_vector = np.zeros((len(self.order_objectives)), dtype='float32')
        enable_target_vector = np.zeros((len(self.order_objectives)), dtype='float32')
        diameter = patch_center[-1]
        is_nodule  = diameter>0.01
        properties['nodule'] = np.float32(is_nodule)
        if is_nodule:
            if 'size' in self.property_bin_borders:
                properties['size'] = np.digitize(diameter, self.property_bin_borders['size'])
            else:
                properties['size'] = diameter
            
            patient = utils_lung.read_patient_annotations_luna(pid, pathfinder.LUNA_NODULE_ANNOTATIONS_PATH)

            #find the nodules in the doctor's annotations
            nodule_characteristics = []
            for doctor in patient:
                for nodule in doctor:
                    if "centroid_xyz" in nodule:
                        dist = self.L2(patch_center[:3],nodule["centroid_xyz"][::-1])
                        if  dist < 5:
                            #print('found a very close nodule at', dist, ': ', patch_center[:3])
                            nodule_characteristics.append(nodule['characteristics'])

            if len(nodule_characteristics)==0:
                print('WARNING: no nodule found in doctor annotations for ', patch_center)
            else:
                #calculate the median property values
                for prop in nodule_characteristics[0]:
                    if prop in self.order_objectives:
                        prop_values = []
                        for nchar in nodule_characteristics:
                            prop_values.append(float(nchar[prop]))
                            random_value = self.rng.choice(np.array(prop_values))
                            if prop in self.property_bin_borders:
                                properties[prop] = np.digitize(random_value, self.property_bin_borders[prop])
                            else:      
                                if self.property_type:
                                    if self.property_type[prop] == 'bounded_continuous':
                                        properties[prop] = (random_value-1) / 4.
                                    else:
                                        properties[prop] = random_value-1
                                else:
                                    raise

        for idx, prop in enumerate(self.order_objectives):
            if prop in properties:
                feature_vector[idx] = properties[prop]
                enable_target_vector[idx] = 1.
            
        return feature_vector, enable_target_vector

    def generate(self):
        while True:
            # Construct pid set with
            rand_pos_idxs = np.arange(self.n_pos_pids)
            rand_neg_idxs = np.arange(self.n_neg_pids)
            ptr_pos_idcs = 0
            ptr_neg_idcs = 0

            if self.random:
                self.rng.shuffle(rand_pos_idxs)
                self.rng.shuffle(rand_neg_idxs)

            n_pos_batch = int(np.rint(self.batch_size * self.positive_proportion))
            n_neg_batch = self.batch_size - n_pos_batch
            for _idx, pos_pos in enumerate(range(0, len(rand_pos_idxs), n_pos_batch)):
                pos_idxs_batch = rand_pos_idxs[pos_pos:pos_pos + n_pos_batch]
                neg_idxs_batch = rand_neg_idxs[_idx * n_neg_batch:(_idx+1) * n_neg_batch]

                nb = len(pos_idxs_batch) + len(neg_idxs_batch)
                # allocate batches
                x_batch = np.zeros((nb,) + self.transform_params['patch_size'], dtype='float32')
                y_batch = np.zeros((nb, len(self.order_objectives)), dtype='float32')
                z_batch = np.zeros((nb, len(self.order_objectives)), dtype='float32')
                patients_ids = []

                batch_ptr = 0
                for idx in pos_idxs_batch:
                    pid  = self.pos_pids[idx]
                    patient_path = self.data_path + '/' + pid + self.file_extension
                    patients_ids.append(pid)

                    img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                        if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)

                    patient_annotations = self.id2positive_annotations[pid]
                    patch_center = patient_annotations[self.rng.randint(len(patient_annotations))]

                    y_batch[batch_ptr], z_batch[batch_ptr] = self.build_ground_truth_vector(pid, patch_center)
                    x_batch[batch_ptr, :, :, :] = self.data_prep_fun(data=img,
                                                                patch_center=patch_center,
                                                                pixel_spacing=pixel_spacing,
                                                                luna_origin=origin)
                    batch_ptr += 1

                for idx in neg_idxs_batch:
                    pid  = self.neg_pids[idx]
                    patient_path = self.data_path + '/' + pid + self.file_extension
                    patients_ids.append(pid)

                    img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                        if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)

                    patient_annotations = self.id2negative_annotations[pid]
                    patch_center = patient_annotations[self.rng.randint(len(patient_annotations))]

                    y_batch[batch_ptr], z_batch[batch_ptr] = self.build_ground_truth_vector(pid, patch_center)
                    x_batch[batch_ptr, :, :, :] = self.data_prep_fun(data=img,
                                                                patch_center=patch_center,
                                                                pixel_spacing=pixel_spacing,
                                                                luna_origin=origin)
                    batch_ptr += 1


                if self.full_batch:
                    if nb == self.batch_size:
                        yield x_batch, y_batch, z_batch, patients_ids
                else:
                    yield x_batch, y_batch, z_batch, patients_ids

            if not self.infinite:
                break


class CandidatesLunaPropsValidDataGenerator(object):
    def __init__(self, data_path, transform_params, patient_ids, data_prep_fun, 
                    order_objectives, property_type, property_bin_borders=None, **kwargs):
        rng = np.random.RandomState(42)  # do not change this!!!

        id2positive_annotations = utils_lung.read_luna_annotations(pathfinder.LUNA_LABELS_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.id2patient_path = {}
        n_positive, n_negative = 0, 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                negative_annotations = id2negative_annotations[pid]
                n_pos = len(id2positive_annotations[pid])
                n_neg = len(id2negative_annotations[pid])
                neg_idxs = rng.choice(n_neg, size=n_pos, replace=False)
                negative_annotations_selected = []
                for i in neg_idxs:
                    negative_annotations_selected.append(negative_annotations[i])
                self.id2negative_annotations[pid] = negative_annotations_selected

                self.id2patient_path[pid] = data_path + '/' + pid + self.file_extension
                n_positive += n_pos
                n_negative += n_pos

        print('n positive', n_positive)
        print('n negative', n_negative)

        self.nsamples = len(self.id2patient_path)
        self.data_path = data_path
        self.rng = rng
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params

        self.order_objectives = order_objectives
        self.property_bin_borders = property_bin_borders
        self.property_type = property_type
    

    def L2(self, a,b):
        return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)**(0.5)


    def build_ground_truth_vector(self, pid, patch_center):
        properties={}
        feature_vector = np.zeros((len(self.order_objectives)), dtype='float32')
        enable_target_vector = np.zeros((len(self.order_objectives)), dtype='float32')
        diameter = patch_center[-1]
        is_nodule  = diameter>0.01
        properties['nodule'] = np.float32(is_nodule)
        if is_nodule:
            if 'size' in self.property_bin_borders:
                properties['size'] = np.digitize(diameter, self.property_bin_borders['size'])
            else:
                properties['size'] = diameter
            
            patient = utils_lung.read_patient_annotations_luna(pid, pathfinder.LUNA_NODULE_ANNOTATIONS_PATH)

            #find the nodules in the doctor's annotations
            nodule_characteristics = []
            for doctor in patient:
                for nodule in doctor:
                    if "centroid_xyz" in nodule:
                        dist = self.L2(patch_center[:3],nodule["centroid_xyz"][::-1])
                        if  dist < 5:
                            #print('found a very close nodule at', dist, ': ', patch_center[:3])
                            nodule_characteristics.append(nodule['characteristics'])

            if len(nodule_characteristics)==0:
                print('WARNING: no nodule found in doctor annotations for ', patch_center)
            else:
                #calculate the median property values
                for prop in nodule_characteristics[0]:
                    if prop in self.order_objectives:
                        prop_values = []
                        for nchar in nodule_characteristics:
                            prop_values.append(float(nchar[prop]))
                        if prop in self.property_bin_borders:
                            median_value = np.median(np.array(prop_values))
                            properties[prop] = np.digitize(median_value, self.property_bin_borders[prop])
                        else:
                            mean_value = np.mean(np.array(prop_values))
                            if self.property_type:
                                if self.property_type[prop] == 'bounded_continuous':
                                    properties[prop] = (mean_value-1) / 4.
                                else:
                                    properties[prop] = mean_value-1
                            else:
                                raise

        for idx, prop in enumerate(self.order_objectives):
            if prop in properties:
                feature_vector[idx] = properties[prop]
                enable_target_vector[idx] = 1.
            
        return feature_vector, enable_target_vector


    def generate(self):

        for pid in self.id2positive_annotations.iterkeys():
            for patch_center in self.id2positive_annotations[pid]:
                patient_path = self.id2patient_path[pid]

                img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                    if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)

                x_batch = np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, :, :, :]

                feature_vector, enable_target_vector = self.build_ground_truth_vector(pid, patch_center)
                y_batch = np.array([feature_vector], dtype='float32')
                z_batch = np.array([enable_target_vector], dtype='float32')

                yield x_batch, y_batch, z_batch, [pid]

            for patch_center in self.id2negative_annotations[pid]:
                patient_path = self.id2patient_path[pid]

                img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                    if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)

                x_batch = np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, :, :, :]

                feature_vector, enable_target_vector = self.build_ground_truth_vector(pid, patch_center)
                y_batch = np.array([feature_vector], dtype='float32')
                z_batch = np.array([enable_target_vector], dtype='float32')

                yield x_batch, y_batch, z_batch, [pid]


class DSBScanDataGenerator(object):
    def __init__(self, data_path, transform_params, data_prep_fun, **kwargs):
        self.patient_paths = utils_lung.get_patient_data_paths(data_path)
        self.nsamples = len(self.patient_paths)
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params

    def generate(self):
        for p in self.patient_paths:
            pid = utils_lung.extract_pid_dir(p)

            img, pixel_spacing = utils_lung.read_dicom_scan(p)

            x, tf_matrix = self.data_prep_fun(data=img, pixel_spacing=pixel_spacing)

            x = np.float32(x)[None, None, :, :, :]
            yield x, None, tf_matrix, pid


class DSBScanLungMaskDataGenerator(object):
    def __init__(self, data_path, transform_params, data_prep_fun, exclude_pids=None,
                 include_pids=None, part_out_of=(1, 1)):

        self.patient_paths = utils_lung.get_patient_data_paths(data_path)

        this_part = part_out_of[0]
        all_parts = part_out_of[1]
        part_lenght = int(len(self.patient_paths) / all_parts)

        if this_part == all_parts:
            self.patient_paths = self.patient_paths[part_lenght * (this_part - 1):]
        else:
            self.patient_paths = self.patient_paths[part_lenght * (this_part - 1): part_lenght * this_part]

        if exclude_pids is not None:
            for ep in exclude_pids:
                for i in range(len(self.patient_paths)):
                    if ep in self.patient_paths[i]:
                        self.patient_paths.pop(i)
                        break

        if include_pids is not None:
            self.patient_paths = [data_path + '/' + p for p in include_pids]

        self.nsamples = len(self.patient_paths)
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params

    def generate(self):
        for p in self.patient_paths:
            pid = utils_lung.extract_pid_dir(p)

            img, pixel_spacing = utils_lung.read_dicom_scan(p)

            x, lung_mask, tf_matrix = self.data_prep_fun(data=img, pixel_spacing=pixel_spacing)

            x = np.float32(x)[None, None, :, :, :]
            lung_mask = np.float32(lung_mask)[None, None, :, :, :]
            yield x, lung_mask, tf_matrix, pid


class CandidatesDSBDataGenerator(object):
    def __init__(self, data_path, transform_params, id2candidates_path, data_prep_fun, exclude_pids=None):
        if exclude_pids is not None:
            for p in exclude_pids:
                id2candidates_path.pop(p, None)

        self.id2candidates_path = id2candidates_path
        self.id2patient_path = {}
        for pid in id2candidates_path.keys():
            self.id2patient_path[pid] = data_path + '/' + pid

        self.nsamples = len(self.id2patient_path)
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params

    def generate(self):

        for pid in self.id2candidates_path.iterkeys():
            patient_path = self.id2patient_path[pid]
            print(pid, patient_path)
            img, pixel_spacing = utils_lung.read_dicom_scan(patient_path)

            print(self.id2candidates_path[pid])
            candidates = utils.load_pkl(self.id2candidates_path[pid])
            print(candidates.shape)
            for candidate in candidates:
                y_batch = np.array(candidate, dtype='float32')
                patch_center = candidate[:3]
                x_batch = np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing))[None, :, :, :]

                yield x_batch, y_batch, [pid]




class CandidatesDSBDataGeneratorTTA(object):
    def __init__(self, data_path, transform_params, id2candidates_path, data_prep_fun, exclude_pids=None, tta=64):
        if exclude_pids is not None:
            for p in exclude_pids:
                id2candidates_path.pop(p, None)

        self.id2candidates_path = id2candidates_path
        self.id2patient_path = {}
        for pid in id2candidates_path.keys():
            self.id2patient_path[pid] = data_path + '/' + pid

        self.nsamples = len(self.id2patient_path)
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.tta = tta

    def generate(self):

        for pid in self.id2candidates_path.iterkeys():
            patient_path = self.id2patient_path[pid]
            print(pid, patient_path)
            img, pixel_spacing = utils_lung.read_dicom_scan(patient_path)

            print(self.id2candidates_path[pid])
            candidates = utils.load_pkl(self.id2candidates_path[pid])
            print(candidates.shape)
            for candidate in candidates:
                y_batch = np.array(candidate, dtype='float32')
                patch_center = candidate[:3]
                batch = []
                for i in range(self.tta):
                    batch.append(np.float32(self.data_prep_fun(data=img,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing)))
                x_batch = np.stack(batch)
                print(x_batch.shape)

                yield x_batch, y_batch, [pid]


class DSBFeatureDataGenerator(object):
    def __init__(self, data_path, batch_size, p_features,
                 rng, random, infinite, patient_ids=None):

        print('init DSBFeatureDataGenerator')

        self.id2label = utils_lung.read_labels(pathfinder.LABELS_PATH)
        self.patient_paths = []
        if patient_ids is not None:
            for pid in patient_ids:
                self.patient_paths.append(data_path + '/' + pid)
        else:
            raise ValueError('provide patient ids')

        self.nsamples = len(self.patient_paths)
        self.data_path = data_path
        self.batch_size = batch_size

        self.p_features = p_features
        self.rng = rng
        self.random = random
        self.infinite = infinite

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)

            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]

                x_batch = np.zeros((self.batch_size,)
                                   + self.p_features['output_shape'], dtype='float32')

                y_batch = np.zeros((self.batch_size,), dtype='float32')
                
                pids_batch = []

                for i, idx in enumerate(idxs_batch):
                    patient_path = self.patient_paths[idx]
                    pid = utils_lung.extract_pid_dir(patient_path)

                    t_features = utils.load_pkl(patient_path+'.pkl')
                    if 'reshape' in self.p_features:
                        t_features = np.reshape(t_features, self.p_features['reshape'])
                    if 'swapaxes' in self.p_features:
                        t_features = np.swapaxes(t_features, *self.p_features['swapaxes'])


                    x_batch[i] = t_features

                    y_batch[i] = self.id2label.get(pid)
                    
                    pids_batch.append(pid)

                if len(idxs_batch) == self.batch_size:
                    yield x_batch, y_batch, pids_batch

            if not self.infinite:
                break

class DSBPatientsDataGenerator(object):
    def __init__(self, data_path, batch_size, transform_params, id2candidates_path, id2label, data_prep_fun,
                 n_candidates_per_patient, rng, random, infinite, candidates_prep_fun, return_patch_locs=False, shuffle_top_n=False, patient_ids=None):

        self.id2label = id2label #utils_lung.read_labels(pathfinder.LABELS_PATH)
        self.id2candidates_path = id2candidates_path
        self.patient_paths = []
        if patient_ids is not None:
            for pid in patient_ids:
                if pid in self.id2candidates_path:  # TODO: this should be redundant if fpr and segemntation are correctly generated
                    self.patient_paths.append(data_path + '/' + pid)
        else:
            raise ValueError('provide patient ids')

        self.nsamples = len(self.patient_paths)
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.batch_size = batch_size
        self.transform_params = transform_params
        self.n_candidates_per_patient = n_candidates_per_patient
        self.rng = rng
        self.random = random
        self.infinite = infinite
        self.shuffle_top_n = shuffle_top_n
        self.return_patch_locs = return_patch_locs
        self.candidates_prep_fun = candidates_prep_fun

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)

            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]

                x_batch = np.zeros((self.batch_size, self.n_candidates_per_patient,)
                                   + self.transform_params['patch_size'], dtype='float32')

                if self.return_patch_locs:
                    x_loc_batch = np.zeros((self.batch_size, self.n_candidates_per_patient, 3), dtype='float32')

                y_batch = np.zeros((self.batch_size,), dtype='float32')
                pids_batch = []

                for i, idx in enumerate(idxs_batch):
                    patient_path = self.patient_paths[idx]
                    pid = utils_lung.extract_pid_dir(patient_path)

                    img, pixel_spacing = utils_lung.read_dicom_scan(patient_path)

                    all_candidates = utils.load_pkl(self.id2candidates_path[pid])
                    if self.candidates_prep_fun:
                        top_candidates = self.candidates_prep_fun(all_candidates, self.n_candidates_per_patient)
                    else:
                        top_candidates = all_candidates[:self.n_candidates_per_patient]
                        if self.shuffle_top_n:
                            self.rng.shuffle(top_candidates)

                    if self.return_patch_locs:
                        #TODO move the normalization to the config file
                        x_loc_batch[i] = np.float32(top_candidates[:,:3])/512. 

                    x_batch[i] = np.float32(self.data_prep_fun(data=img, pid=pid,
                                                               patch_centers=top_candidates,
                                                               pixel_spacing=pixel_spacing))[:, :, :, :]
                    y_batch[i] = self.id2label.get(pid)
                    pids_batch.append(pid)

                if len(idxs_batch) == self.batch_size:
                    if self.return_patch_locs:
                        yield x_batch, x_loc_batch, y_batch, pids_batch
                    else:
                        yield x_batch, y_batch, pids_batch

            if not self.infinite:
                break



class DSBPatientsDataGeneratorTTA(object):
    def __init__(self, data_path, transform_params, id2candidates_path, id2label, data_prep_fun, candidates_prep_fun,
                 n_candidates_per_patient, patient_ids, tta=1):

        self.id2label = id2label 
        self.id2candidates_path = id2candidates_path
        self.patient_paths = []
        if patient_ids is not None:
            for pid in patient_ids:
                if pid in self.id2candidates_path:  # TODO: this should be redundant if fpr and segemntation are correctly generated
                    self.patient_paths.append(data_path + '/' + pid)
        else:
            raise ValueError('provide patient ids')

        self.nsamples = len(self.patient_paths)
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.n_candidates_per_patient = n_candidates_per_patient
        self.tta = tta
        self.candidates_prep_fun = candidates_prep_fun

    def generate(self):
        print()
        for idx in range(self.nsamples):
            x_batch = np.zeros((self.tta, self.n_candidates_per_patient,)
                               + self.transform_params['patch_size'], dtype='float32')

            y_batch = np.zeros((self.tta,), dtype='float32')

            patient_path = self.patient_paths[idx]
            pid = utils_lung.extract_pid_dir(patient_path)

            img, pixel_spacing = utils_lung.read_dicom_scan(patient_path)

            all_candidates = utils.load_pkl(self.id2candidates_path[pid])
            if self.candidates_prep_fun:
                top_candidates = self.candidates_prep_fun(all_candidates, self.n_candidates_per_patient)
            else:
                top_candidates = all_candidates[:self.n_candidates_per_patient]

            for i in range(self.tta):
                x_batch[i] = np.float32(self.data_prep_fun(data=img,
                                                           patch_centers=top_candidates,
                                                           pixel_spacing=pixel_spacing))[:, :, :, :]

                y_batch[i] = self.id2label.get(pid)

            yield x_batch, y_batch, pid




class DSBPixelSpacingsGenerator(object):
    def __init__(self, data_path, id2candidates_path, patient_ids):

        self.id2candidates_path = id2candidates_path
        self.patient_paths = []
        if patient_ids is not None:
            for pid in patient_ids:
                if pid in self.id2candidates_path:  # TODO: this should be redundant if fpr and segemntation are correctly generated
                    self.patient_paths.append(data_path + '/' + pid)
        else:
            raise ValueError('provide patient ids')

        self.nsamples = len(self.patient_paths)
        self.data_path = data_path

    def generate(self):

        for idx in range(self.nsamples):

            patient_path = self.patient_paths[idx]
            pid = utils_lung.extract_pid_dir(patient_path)

            img, pixel_spacing = utils_lung.read_dicom_scan(patient_path)

            yield  pid, pixel_spacing


class DSBPatientsDataGenerator_only_heatmap(object):
    def __init__(self, data_path, batch_size, transform_params, id2candidates_path, data_prep_fun, 
                 n_candidates_per_patient, rng, random, infinite, candidates_prep_fun, return_patch_locs=False, shuffle_top_n=False, patient_ids=None):

        self.id2label = utils_lung.read_labels(pathfinder.LABELS_PATH)
        self.id2candidates_path = id2candidates_path
        self.patient_paths = []
        if patient_ids is not None:
            for pid in patient_ids:
                if pid in self.id2candidates_path:  # TODO: this should be redundant if fpr and segemntation are correctly generated
                    self.patient_paths.append(data_path + '/' + pid)
        else:
            raise ValueError('provide patient ids')

        self.nsamples = len(self.patient_paths)
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.batch_size = batch_size
        self.transform_params = transform_params
        self.rng = rng
        self.random = random
        self.infinite = infinite
        self.shuffle_top_n = shuffle_top_n
        self.candidates_prep_fun = candidates_prep_fun
        self.n_candidates_per_patient = n_candidates_per_patient

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)

            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]

                x_batch = np.zeros((self.batch_size,)
                                   + self.transform_params['heatmap_size'], dtype='float32')

                y_batch = np.zeros((self.batch_size,), dtype='float32')
                pids_batch = []

                for i, idx in enumerate(idxs_batch):
                    patient_path = self.patient_paths[idx]
                    pid = utils_lung.extract_pid_dir(patient_path)

                    img, pixel_spacing = utils_lung.read_dicom_scan(patient_path)

                    all_candidates = utils.load_pkl(self.id2candidates_path[pid])
                    candidates_w_value = self.candidates_prep_fun(all_candidates)

                    x_batch[i] = np.float32(self.data_prep_fun(data=img,
                                                               candidates=candidates_w_value,
                                                               pixel_spacing=pixel_spacing))
                    y_batch[i] = self.id2label.get(pid)
                    pids_batch.append(pid)

                if len(idxs_batch) == self.batch_size:
                    yield x_batch, y_batch, pids_batch

            if not self.infinite:
                break


class DSBPatientsDataGeneratorRandomSelectionNonCancerous(object):
    def __init__(self, data_path, batch_size, transform_params, id2candidates_path, data_prep_fun,
                 n_candidates_per_patient, rng, random, infinite, top_true=10, top_false=16, shuffle_top_n=False, patient_ids=None):

        self.id2label = utils_lung.read_labels(pathfinder.LABELS_PATH)
        self.id2candidates_path = id2candidates_path
        self.patient_paths = []
        if patient_ids is not None:
            for pid in patient_ids:
                if pid in self.id2candidates_path:  # TODO: this should be redundant if fpr and segemntation are correctly generated
                    self.patient_paths.append(data_path + '/' + pid)
        else:
            raise ValueError('provide patient ids')

        self.nsamples = len(self.patient_paths)
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.batch_size = batch_size
        self.transform_params = transform_params
        self.n_candidates_per_patient = n_candidates_per_patient
        self.rng = rng
        self.random = random
        self.infinite = infinite
        self.shuffle_top_n = shuffle_top_n
        self.top_true = top_true
        self.top_false = top_false  

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)

            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]

                x_batch = np.zeros((self.batch_size, self.n_candidates_per_patient, 1,)
                                   + self.transform_params['patch_size'], dtype='float32')
                y_batch = np.zeros((self.batch_size,), dtype='float32')
                pids_batch = []

                for i, idx in enumerate(idxs_batch):
                    patient_path = self.patient_paths[idx]
                    pid = utils_lung.extract_pid_dir(patient_path)

                    img, pixel_spacing = utils_lung.read_dicom_scan(patient_path)
                    all_candidates = utils.load_pkl(self.id2candidates_path[pid])

                    label = self.id2label.get(pid)
                    if label:
                        top_candidates = all_candidates[:self.n_candidates_per_patient]
                    else:
                        selection = np.arange(self.top_false)
                        self.rng.shuffle(selection)
                        selection = selection[:self.n_candidates_per_patient]
                        top_candidates = all_candidates[selection]

                    
                    if self.shuffle_top_n:
                        self.rng.shuffle(top_candidates)

                    x_batch[i] = np.float32(self.data_prep_fun(data=img,
                                                               patch_centers=top_candidates,
                                                               pixel_spacing=pixel_spacing))[:, None, :, :, :]
                    y_batch[i] = label
                    pids_batch.append(pid)

                if len(idxs_batch) == self.batch_size:
                    yield x_batch, y_batch, pids_batch

            if not self.infinite:
                break

#balance between patients with and without cancer
class BalancedDSBPatientsDataGenerator(object):
    def __init__(self, data_path, batch_size, transform_params, id2candidates_path, data_prep_fun,
                 n_candidates_per_patient, rng, random, infinite, shuffle_top_n=False, patient_ids=None):

        self.id2label = utils_lung.read_labels(pathfinder.LABELS_PATH)
        self.id2candidates_path = id2candidates_path
        self.patient_paths = []
        if patient_ids is not None:
            for pid in patient_ids:
                if pid in self.id2candidates_path:  # TODO: this should be redundant if fpr and segemntation are correctly generated
                    self.patient_paths.append(data_path + '/' + pid)
        else:
            raise ValueError('provide patient ids')
        self.pos_ids = []
        self.neg_ids = []
        for pid in patient_ids:
            if self.id2label[pid]:
                self.pos_ids.append(pid)
            else:
                self.neg_ids.append(pid)
        self.n_pos_ids = len(self.pos_ids)
        self.n_neg_ids = len(self.neg_ids)
        print('n positive ids', self.n_pos_ids)
        print('n negative ids', self.n_neg_ids)
        self.all_pids = patient_ids
        self.nsamples = len(self.all_pids)

        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.batch_size = batch_size
        self.transform_params = transform_params
        self.n_candidates_per_patient = n_candidates_per_patient
        self.rng = rng
        self.random = random
        self.infinite = infinite
        self.shuffle_top_n = shuffle_top_n

    def generate(self):
        while True:
            neg_rand_idxs = np.arange(self.n_neg_ids)
            if self.random:
                self.rng.shuffle(neg_rand_idxs)
            neg_rand_idxs_ptr = 0
            batch_pids = []
            while(neg_rand_idxs_ptr<self.n_neg_ids):               
                if self.rng.randint(2):
                    #take a cancerous patient
                    pos_pid = self.rng.choice(self.pos_ids)
                    batch_pids.append(pos_pid)
                else:
                    neg_pid = self.neg_ids[neg_rand_idxs[neg_rand_idxs_ptr]] 
                    batch_pids.append(neg_pid)
                    neg_rand_idxs_ptr += 1
                if len(batch_pids)==self.batch_size:
                    yield self.prepare_batch(batch_pids)
                    batch_pids = []
            # yield the half filled batch
            if len(batch_pids) > 0:
                yield self.prepare_batch(batch_pids)

            if not self.infinite:
                break

    def prepare_batch(self, batch_pids):
        x_batch = np.zeros((len(batch_pids), self.n_candidates_per_patient, 1,)
                               + self.transform_params['patch_size'], dtype='float32')
        y_batch = np.zeros((len(batch_pids),), dtype='float32')
        for i, pid in enumerate(batch_pids):
            patient_path = self.data_path + '/' + str(pid)
            img, pixel_spacing = utils_lung.read_dicom_scan(patient_path)  
            all_candidates = utils.load_pkl(self.id2candidates_path[pid])
            top_candidates = all_candidates[:self.n_candidates_per_patient]                       
            if self.shuffle_top_n:
                self.rng.shuffle(top_candidates)
            x_batch[i] = np.float32(self.data_prep_fun(data=img,
                                                   patch_centers=top_candidates,
                                                   pixel_spacing=pixel_spacing))[:, None, :, :, :]
            y_batch[i] = self.id2label.get(pid) 
        return x_batch, y_batch, batch_pids

class DSBDataGenerator(object):
    def __init__(self, data_path, transform_params=None, data_prep_fun=None, patient_pids=None, **kwargs):
        self.patient_paths = utils_lung.get_patient_data_paths(data_path)


        self.patient_paths = [data_path + '/' + p for p in patient_pids]

        self.nsamples = len(self.patient_paths)
        self.data_path = data_path
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params

    def generate(self):
        for p in self.patient_paths:
            pid = utils_lung.extract_pid_dir(p)

            img, pixel_spacing = utils_lung.read_dicom_scan(p)

            if self.data_prep_fun:
                x, tf_matrix = self.data_prep_fun(data=img, pixel_spacing=pixel_spacing)
            else:
                x = img

            x = np.float32(x)
            yield x,  pid




class CandidatesPropertiesLunaDataGenerator(object):
    def __init__(self, data_path, batch_size, transform_params, label_prep_fun,
                 nproperties,  patient_ids, data_prep_fun, rng,
                 full_batch, random, infinite, positive_proportion, properties_included=[],
                 random_negative_samples=False, **kwargs):

        id2positive_annotations = utils_lung.read_luna_properties(pathfinder.LUNA_PROPERTIES_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.pid2patient_path = {}
        n_positive = 0
        for pid in patient_ids:
            self.pid2patient_path[pid] = data_path + '/' + pid + self.file_extension
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                n_positive += len(id2positive_annotations[pid])
            if pid in id2negative_annotations:
                self.id2negative_annotations[pid] = id2negative_annotations[pid]

        self.nsamples = int(n_positive + (1. - positive_proportion) / positive_proportion * n_positive)
        print('n samples', self.nsamples)
        self.idx2pid_annotation = {}
        i = 0
        for pid, annotations in self.id2positive_annotations.iteritems():
            for a in annotations:
                self.idx2pid_annotation[i] = (pid, a)
                i += 1
        print('n positive', len(self.idx2pid_annotation.keys()))

        if random_negative_samples:
            while i < self.nsamples:
                self.idx2pid_annotation[i] = (None, None)
                i += 1
        else:
            while i < self.nsamples:
                pid = rng.choice(self.id2negative_annotations.keys())
                patient_annotations = self.id2negative_annotations[pid]
                a = patient_annotations[rng.randint(len(patient_annotations))]
                self.idx2pid_annotation[i] = (pid, a)
                i += 1
        assert len(self.idx2pid_annotation) == self.nsamples

        self.data_path = data_path
        self.batch_size = batch_size
        self.rng = rng
        self.full_batch = full_batch
        self.random = random
        self.infinite = infinite
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.positive_proportion = positive_proportion
        self.label_prep_fun = label_prep_fun
        self.nlabels = nproperties

        if len(properties_included)>0:
            self.nlabels=len(properties_included)
        self.properties_included = properties_included

        assert self.transform_params['pixel_spacing'] == (1., 1., 1.)

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]
                nb = len(idxs_batch)
                # allocate batches
                x_batch = np.zeros((nb,) + self.transform_params['patch_size'], dtype='float32')
                y_batch = np.zeros((nb, self.nlabels), dtype='float32')
                patients_ids = []

                for i, idx in enumerate(idxs_batch):
                    pid, patch_annotation = self.idx2pid_annotation[idx]

                    if pid is None:
                        pid = self.rng.choice(self.id2negative_annotations.keys())
                        patient_annotations = self.id2negative_annotations[pid]
                        patch_annotation = patient_annotations[self.rng.randint(len(patient_annotations))]

                    patient_path = self.pid2patient_path[pid]
                    patients_ids.append(pid)

                    y_batch[i] = self.label_prep_fun(patch_annotation,self.properties_included)
                    # print(pid, y_batch[i])

                    img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                        if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)

                    patch_zyxd = patch_annotation[:4]
                    x_batch[i, :, :, :] = self.data_prep_fun(data=img, pid = pid,
                                                                patch_center=patch_zyxd,
                                                                pixel_spacing=pixel_spacing,
                                                                luna_origin=origin)
                y_batch = np.asarray(y_batch,dtype=np.float32)
                if self.full_batch:
                    if nb == self.batch_size:
                        yield x_batch, y_batch, patients_ids
                else:
                    yield x_batch, y_batch, patients_ids

            if not self.infinite:
                break


class CandidatesPropertiesLunaDataGenerator2(object):
    def __init__(self, data_path, batch_size, transform_params, label_prep_fun,
                 nproperties,  patient_ids, data_prep_fun, rng,
                 full_batch, random, infinite, positive_proportion, properties_included=[],
                 random_negative_samples=False, **kwargs):

        id2positive_annotations = utils_lung.read_luna_properties(pathfinder.LUNA_PROPERTIES_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.pid2patient_path = {}
        n_positive = 0
        for pid in patient_ids:
            self.pid2patient_path[pid] = data_path + '/' + pid + self.file_extension
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                n_positive += len(id2positive_annotations[pid])
            if pid in id2negative_annotations:
                self.id2negative_annotations[pid] = id2negative_annotations[pid]

        self.nsamples = int(n_positive + (1. - positive_proportion) / positive_proportion * n_positive)
        print('n samples', self.nsamples)
        self.idx2pid_annotation = {}
        i = 0
        for pid, annotations in self.id2positive_annotations.iteritems():
            for a in annotations:
                self.idx2pid_annotation[i] = (pid, a)
                i += 1
        print('n positive', len(self.idx2pid_annotation.keys()))

        if random_negative_samples:
            while i < self.nsamples:
                self.idx2pid_annotation[i] = (None, None)
                i += 1
        else:
            while i < self.nsamples:
                pid = rng.choice(self.id2negative_annotations.keys())
                patient_annotations = self.id2negative_annotations[pid]
                a = patient_annotations[rng.randint(len(patient_annotations))]
                self.idx2pid_annotation[i] = (pid, a)
                i += 1
        assert len(self.idx2pid_annotation) == self.nsamples

        self.data_path = data_path
        self.batch_size = batch_size
        self.rng = rng
        self.full_batch = full_batch
        self.random = random
        self.infinite = infinite
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.positive_proportion = positive_proportion
        self.label_prep_fun = label_prep_fun
        self.nlabels = nproperties

        if len(properties_included)>0:
            self.nlabels=len(properties_included)
        self.properties_included = properties_included

        assert self.transform_params['pixel_spacing'] == (1., 1., 1.)

    def generate(self):
        while True:
            rand_idxs = np.arange(self.nsamples)
            if self.random:
                self.rng.shuffle(rand_idxs)
            for pos in range(0, len(rand_idxs), self.batch_size):
                idxs_batch = rand_idxs[pos:pos + self.batch_size]
                nb = len(idxs_batch)
                # allocate batches
                x_batch = np.zeros((nb,) + self.transform_params['patch_size'], dtype='float32')
                if self.nlabels == 1:
                    y_batch = np.zeros((nb,), dtype='float32')
                else:
                    y_batch = np.zeros((nb, self.nlabels), dtype='float32')
                patients_ids = []

                for i, idx in enumerate(idxs_batch):
                    pid, patch_annotation = self.idx2pid_annotation[idx]

                    if pid is None:
                        pid = self.rng.choice(self.id2negative_annotations.keys())
                        patient_annotations = self.id2negative_annotations[pid]
                        patch_annotation = patient_annotations[self.rng.randint(len(patient_annotations))]

                    patient_path = self.pid2patient_path[pid]
                    patients_ids.append(pid)

                    y_batch[i] = self.label_prep_fun(patch_annotation,self.properties_included)
                    # print(pid, y_batch[i])

                    img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                        if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)

                    patch_zyxd = patch_annotation[:4]
                    x_batch[i, :, :, :] = self.data_prep_fun(data=img, pid = pid,
                                                                patch_center=patch_zyxd,
                                                                pixel_spacing=pixel_spacing,
                                                                luna_origin=origin)
                y_batch = np.asarray(y_batch,dtype=np.float32)
                if self.full_batch:
                    if nb == self.batch_size:
                        yield x_batch, y_batch, patients_ids
                else:
                    yield x_batch, y_batch, patients_ids

            if not self.infinite:
                break


class CandidatesLunaValidDataGenerator2(object):
    def __init__(self, data_path, transform_params, patient_ids, data_prep_fun, label_prep_fun=None,properties_included=[],
                 **kwargs):
        rng = np.random.RandomState(42)  # do not change this!!!

        id2positive_annotations = utils_lung.read_luna_properties(pathfinder.LUNA_PROPERTIES_PATH)
        id2negative_annotations = utils_lung.read_luna_negative_candidates(pathfinder.LUNA_CANDIDATES_PATH)

        self.file_extension = '.pkl' if 'pkl' in data_path else '.mhd'
        self.id2positive_annotations = {}
        self.id2negative_annotations = {}
        self.id2patient_path = {}
        n_positive, n_negative = 0, 0
        for pid in patient_ids:
            if pid in id2positive_annotations:
                self.id2positive_annotations[pid] = id2positive_annotations[pid]
                negative_annotations = id2negative_annotations[pid]
                n_pos = len(id2positive_annotations[pid])
                n_neg = len(id2negative_annotations[pid])
                neg_idxs = rng.choice(n_neg, size=n_pos, replace=False)
                negative_annotations_selected = []
                for i in neg_idxs:
                    negative_annotations_selected.append(negative_annotations[i])
                self.id2negative_annotations[pid] = negative_annotations_selected

                self.id2patient_path[pid] = data_path + '/' + pid + self.file_extension
                n_positive += n_pos
                n_negative += n_pos

        print('n positive', n_positive)
        print('n negative', n_negative)

        self.nsamples = len(self.id2patient_path)
        self.data_path = data_path
        self.rng = rng
        self.data_prep_fun = data_prep_fun
        self.transform_params = transform_params
        self.label_prep_fun = label_prep_fun
        if label_prep_fun is not None:
            assert self.transform_params['pixel_spacing'] == (1., 1., 1.)

        self.properties_included = properties_included

    def generate(self):

        for pid in self.id2positive_annotations.iterkeys():
            for patch_center in self.id2positive_annotations[pid]:
                patient_path = self.id2patient_path[pid]

                img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                    if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                if self.label_prep_fun is None:
                    y_batch = np.array([1.], dtype='float32')
                else:
                    y_batch = np.array([self.label_prep_fun(patch_center,self.properties_included)], dtype='float32')
                x_batch = np.float32(self.data_prep_fun(data=img, pid=pid,
                                                        patch_center=patch_center[0:4],
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, :, :, :]

                yield x_batch, y_batch, [pid]

            for patch_center in self.id2negative_annotations[pid]:
                patient_path = self.id2patient_path[pid]

                img, origin, pixel_spacing = utils_lung.read_pkl(patient_path) \
                    if self.file_extension == '.pkl' else utils_lung.read_mhd(patient_path)
                y_batch = np.array([0.], dtype='float32')
                x_batch = np.float32(self.data_prep_fun(data=img, pid=pid,
                                                        patch_center=patch_center,
                                                        pixel_spacing=pixel_spacing,
                                                        luna_origin=origin))[None, :, :, :]

                yield x_batch, y_batch, [pid]