#!/usr/bin/env python3

"""
Encounter+ Image/Token Adder
"""

__author__ = "Sebastian Goscik"
__version__ = "0.1.0"
__license__ = "MIT"

import argparse
import os
import logging
import sys
import tempfile
import shutil
import random
import string
import re

from xml.etree import ElementTree
from zipfile import ZipFile
from fuzzywuzzy import fuzz
from difflib import SequenceMatcher

logging.DETAILED = 15
logger = logging.getLogger(__name__)
logging.addLevelName(logging.DETAILED, "DETAILED")


def detailed(self, message, *args, **kws):
    if self.isEnabledFor(15):
        self._log(15, message, args, **kws)


logging.Logger.detailed = detailed

sub_directories = {
    "monster": "monsters",
    "item": "items",
}


def find_images(path):
    images = []
    for root_dir, dirs, files in os.walk(path):
        for f in files:
            image_name, ext = os.path.splitext(f)
            if ext.lower() in ['.jpg', '.jpeg', '.png']:
                found_image = (root_dir, image_name, ext)
                images.append(found_image)
                logging.debug("Image found: {}".format(found_image))
    return images


def find_best_match(images, name):
    # Calculate match ratios
    ratios = []
    for dir_path, file_name, ext in images:
        # Strip out non alphanumeric chatacters from file name to improve matching
        non_alphanumeric_regex = re.compile(r'[\W _]+')
        cleaned_file_name = non_alphanumeric_regex.sub('', file_name)

        ratio = fuzz.ratio(cleaned_file_name, name)
        ratios.append((ratio, (dir_path, file_name, ext)))

    # Get best match
    return max(ratios, key=lambda item: item[0])


def main(args):
    logger.debug("Args={}".format(args))

    _, extension = os.path.splitext(args.compendium_path)

    if(extension.lower() not in [".zip", ".compendium", ".xml"]):
        msg = "Invalid file format ({}), please provide a `.xml`, `.compendium` or `.zip` file"
        logger.error(msg.format(extension))
        sys.exit(1)

    if not os.path.exists(args.compendium_path):
        msg = "Provided file path ({}) does not exist".format(args.compendium_path)
        logger.error(msg)
        sys.exit(1)

    # Create output file
    with ZipFile(args.output_path, mode="w") as output_zip:
        with tempfile.TemporaryDirectory() as temp_dir:

            # The file provided is compressed, need to decompress it first
            if(extension.lower() in [".zip", ".compendium"]):
                logger.info("Decompressing archive")
                zip_file = ZipFile(os.path.abspath(args.compendium_path))
                zip_file.extractall(temp_dir)

                xml_path = os.path.join(temp_dir, "compendium.xml")
                if not os.path.exists(xml_path):
                    msg = "Provided archive ({}) does not contain a `compendium.xml` file."
                    logger.error(msg.format(args.compendium_path))
                    sys.exit(1)

                # Add extracted files to output compendium
                for root_dir, dirs, files in os.walk(temp_dir):
                    for f in files:
                        #Skip compendium file, since it will be updated
                        if f == "compendium.xml":
                            continue
                        src_path = os.path.join(root_dir, f)
                        output_zip.write(src_path, os.path.relpath(src_path, start=temp_dir))
            else:
                xml_path = args.compendium_path

            logger.debug("XML File: {}".format(xml_path))

            # Find all image files
            logging.info("Identifying Images")
            images = find_images(args.image_path)

            logging.info("Parsing XML")

            tree = ElementTree.parse(xml_path)
            root = tree.getroot()

            logging.info("Searching for Monsters and Items")
            for node in root.findall("*"):
                # Check if this is a compendium entry that supports images
                if node.tag not in ["monster", "item"]:
                    logging.debug("Ignoring `{}` Tag".format(node.tag))
                    continue

                tag_name = node.find("name").text
                logging.debug("Found `{}`: {}".format(node.tag, tag_name))

                # Check if compendium entry already has an image
                if node.find("image") is not None:
                    logging.debug("Already has an image")
                    continue

                match_ratio, image_file_path_info = find_best_match(images, tag_name)

                image_file_name = image_file_path_info[1] + image_file_path_info[2]
                image_file_src = os.path.join(image_file_path_info[0], image_file_name)

                # Automatic Match
                if match_ratio >= args.auto_ratio:
                    logger.detailed("Found image for '{}': {}".format(tag_name, image_file_src))

                # Partial Match
                elif match_ratio >= args.ask_ratio:
                    msg = "Found potential match ({}) for '{}': {}"
                    logger.info(msg.format(match_ratio, tag_name, image_file_src))

                    # Ask user if partial match is correct
                    choice = input("Use this file? y/n (default: y): ")
                    while choice not in ["n", "y", "Y", ""]:
                        msg = "Invalid input `{}`, please use `n`, `y` (default: `y`): "
                        choice = input(msg.format(choice))
                    if choice == "n":
                        continue

                # No Match
                else:
                    logger.debug("No match found")
                    continue

                # If a file of the same name already exists in the output zip, add a random string
                # to the file name until it is unique
                image_file_dst = os.path.join(sub_directories[node.tag],  image_file_name)
                while image_file_dst in output_zip.namelist():
                    random_str = ''.join(random.choices(string.ascii_lowercase, k=6))
                    image_file_name = "{}_{}{}".format(image_file_path_info[1],
                                                       random_str,
                                                       image_file_path_info[2])
                    image_file_dst = os.path.join(sub_directories[node.tag],  image_file_name)

                # Add image to compendium
                ElementTree.SubElement(node, "image").text = image_file_name
                output_zip.write(image_file_src, arcname=image_file_dst)
                logging.debug("File written to: `{}`".format(image_file_dst))

            # Add xml to the output zip
            logging.info("Outputting Compendium")
            output_zip.writestr('compendium.xml', ElementTree.tostring(root))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add images and tokens to Encounter+ compendium '
                                                 'using a fuzzy search algorithm.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('compendium_path', metavar='COMPENDIUM_PATH',
                        help='Path to compendium file, valid formats: XML, Compendium, Zip')
    parser.add_argument('image_path', metavar='IMAGE_PATH',
                        help='Path to image files, valid formats: PNG, JPEG')
    parser.add_argument('token_path', nargs='?', metavar='TOKEN_PATH',
                        help='OPTIONAL - Path to token files, valid formats: PNG, JPEG')

    parser.add_argument("-o", "--output", action="store", dest="output_path",
                        default="with_images.compendium", type=str,
                        help="How much similarity there has to be between the compendium entry name"
                             " and the file name for an automatic match."
                             " Range 0-100, if set to 1, only exact matches will be used.")
    parser.add_argument("-m", "--match", action="store", dest="auto_ratio", default=80, type=float,
                        help="How much similarity there has to be between the compendium entry name"
                             " and the file name for an automatic match."
                             " Range 0-100, if set to 1, only exact matches will be used.")
    parser.add_argument("-a", "--ask", action="store", dest="ask_ratio", default=50, type=float,
                        help="How much similarity there has to be between the compendium entry name"
                             " and the file name for the script to ask the user for confirmation."
                             " Range 0-1.0, this should be lower than `match` otherwise this"
                             " feature is dsabled.")
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity (-v, -vv, etc)")

    # Specify output of "--version"
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (version {version})".format(version=__version__))

    args = parser.parse_args()

    if args.verbose == 1:
        logging.basicConfig(stream=sys.stdout, level=logging.DETAILED)
    elif args.verbose == 2:
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    try:
        main(args)
    except Exception as e:
        logger.exception("Unhandled error occured", exc_info=True)
