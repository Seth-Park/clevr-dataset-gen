import argparse, json, os
from collections import defaultdict
from tqdm import tqdm

"""
Captions are generated in a parallel manner, resulting in multiple json files.
This script collects these json files and combines them into a single file.
"""

parser = argparse.ArgumentParser()
parser.add_argument('--input_dir', default='output/captions')
parser.add_argument('--output_file', default='output/CLEVR_captions.json')

def main(args):
    input_files = os.listdir(args.input_dir)
    img_to_caps = defaultdict(lambda : [])
    split = None

    for filename in tqdm(input_files):
        path = os.path.join(args.input_dir, filename)
        with open(path, 'r') as f:
            caps = json.load(f)['questions']
        for cap in caps:
            if split is not None:
                msg = 'Input directory contains captions from multiple splits'
                assert cap['split'] == split, msg
            else:
                split = cap['split']
            img_filename = cap['image_filename']
            text = cap['question']
            img_to_caps[img_filename].append(text)

    with open(args.output_file, 'w') as f:
        json.dump(img_to_caps, f)

if __name__ == '__main__':
    args = parser.parse_args()
    main(args)
    
