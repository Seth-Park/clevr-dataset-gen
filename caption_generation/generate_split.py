import json
import random
import os

CAP_JSON = '/data2/seth/data/semantic_change/output_combined/change_captions.json'
RESULT_FILE = '/data2/seth/data/semantic_change/output_combined/splits.json'
captions = json.load(open(CAP_JSON, 'r'))
total_imgs = len(captions)
imgs = sorted(list(captions.keys()))
indices = [int(img.split('_')[-1].split('.')[0]) for img in imgs]
train_len = int(total_imgs * 0.9)
val_len = int(total_imgs * 0.05)
test_len = total_imgs - (train_len + val_len)
assert (train_len + val_len + test_len) == total_imgs

random.seed(123)
random.shuffle(indices)
train_idx = indices[:train_len]
val_idx = indices[train_len : train_len + val_len]
test_idx = indices[train_len + val_len:]

assert len(set(train_idx).intersection(val_idx)) == 0
assert len(set(train_idx).intersection(test_idx)) == 0
assert len(set(test_idx).intersection(val_idx)) == 0

assert len(train_idx) == train_len
assert len(val_idx) == val_len
assert len(test_idx) == test_len

split = {'train': train_idx, 'val': val_idx, 'test': test_idx}
with open(RESULT_FILE, 'w') as f:
    json.dump(split, f)
