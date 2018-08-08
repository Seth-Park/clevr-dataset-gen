import argparse, json, os
from collections import defaultdict
from tqdm import tqdm

"""
Captions are generated separately for different tasks
(i.e. color change, material change etc.) so they should be merged if training
on the entire dataset.
This script collects the caption json files and combines them into a single file.
"""

parser = argparse.ArgumentParser()
parser.add_argument('--input_dir', default='output_combined/captions')
parser.add_argument('--output_file', default='output_combined/change_captions.json')

def main(args):
    input_files = os.listdir(args.input_dir)
    img_to_caps = {}
    count = 0

    for filename in tqdm(input_files):
        path = os.path.join(args.input_dir, filename)
        with open(path, 'r') as f:
            caps = json.load(f)
        newly_added = len(caps)
        img_to_caps.update(caps)
        count += newly_added
        assert count == len(img_to_caps), 'Overlaping keys when merging %s' % filename

    with open(args.output_file, 'w') as f:
        json.dump(img_to_caps, f)

if __name__ == '__main__':
    args = parser.parse_args()
    main(args)
    
