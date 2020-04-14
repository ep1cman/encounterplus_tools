# Encounter Plus Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This is a repo of tools I have created for use with the [EncounterPlus](http://encounter.plus) app.

Before using any of these scripts be sure to run the following command to install their requirements:

```
pip install -r requirements.txt
```

# add_images

This tool uses a fuzzy match algorithm to help automate adding images and/or tokens to Monster and Item entries in compendium files.

```
usage: add_images.py [-h] [-i IMAGE_PATH] [-t TOKEN_PATH] [-o OUTPUT_PATH] [-m AUTO_PERCENT] [-a ASK_PERCENT] [-v] [--version] COMPENDIUM_PATH

Add images and tokens to Encounter+ compendium using a fuzzy search algorithm.

positional arguments:
  COMPENDIUM_PATH       Path to compendium file, valid formats: .xml, .compendium, .zip

optional arguments:
  -h, --help            show this help message and exit
  -i IMAGE_PATH, --image_path IMAGE_PATH
                        Path to image files, valid formats: PNG, JPEG (default: None)
  -t TOKEN_PATH, --token_path TOKEN_PATH
                        Path to token files, valid formats: PNG, JPEG (default: None)
  -o OUTPUT_PATH, --output OUTPUT_PATH
                        Path of the output compendium archive (default: with_images.compendium)
  -m AUTO_PERCENT, --match AUTO_PERCENT
                        How much similarity there has to be between the compendium entry name and the file name for an automatic match. Range 0-100, if
                        set to 100, only exact matches will be used. (default: 80)
  -a ASK_PERCENT, --ask ASK_PERCENT
                        How much similarity there has to be between the compendium entry name and the file name for the script to ask the user for
                        confirmation. Range 0-100, this should be lower than `match` otherwise this feature is dsabled. (default: 50)
  -v, --verbose         Verbosity (-v, -vv, etc) (default: 0)
  --version             show program's version number and exit
  ```