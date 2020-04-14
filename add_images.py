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


class Quit(Exception):
    pass


def find_images(path):
    images = []
    for root_dir, dirs, files in os.walk(path):
        for f in files:
            if f.endswith(('.jpg', '.jpeg', '.png')):
                found_image = os.path.join(root_dir, f)
                images.append(found_image)
                logging.debug("Image found: {}".format(found_image))
    return images


def find_best_match(images, name, tag):
    # Calculate match ratios
    ratios = []
    for image_path in images:
        # Get just the name of the file without extension
        file_name = os.path.basename(image_path)
        file_name, _ = os.path.splitext(file_name)
        # Strip out non alphanumeric chatacters from file name to improve matching
        non_alphanumeric_regex = re.compile(r'[\W _]+')
        cleaned_file_name = non_alphanumeric_regex.sub('', file_name)
        # Strip out tag name from file name to improve matching e.g goblin_token.png
        tag_regex = re.compile(tag, re.IGNORECASE)
        cleaned_file_name = tag_regex.sub("", cleaned_file_name)

        ratio = fuzz.ratio(cleaned_file_name, name)
        ratios.append((ratio, image_path))

    # return highest match ratio
    return max(ratios, key=lambda item: item[0])


def add_image_to_compendium_zip(path, node_type, output_zip):
    image_file_name = os.path.basename(path)
    image_file_dst = os.path.join(sub_directories[node_type], image_file_name)

    # If a file of the same name already exists in the output zip, add a random string
    # to the file name until it is unique
    while image_file_dst in output_zip.namelist():
        random_str = ''.join(random.choices(string.ascii_lowercase, k=6))
        file_name, extension = os.path.splitext(image_file_name)
        image_file_name = "{}_{}{}".format(file_name, random_str, extension)
        image_file_dst = os.path.join(sub_directories[node_type],  image_file_name)

    # Add image to compendium
    output_zip.write(path, arcname=image_file_dst)
    logging.debug("File written to: `{}`".format(image_file_dst))


def match(tag, name, images, auto_ratio, ask_ratio):
    match_ratio, image_file = find_best_match(images, name, tag)

    # Automatic Match
    if match_ratio >= auto_ratio:
        logger.detailed("Found {} for '{}': {}".format(tag, name, image_file))

    # Partial Match
    elif match_ratio >= ask_ratio:
        msg = "Found potential {} ({}) for '{}': {}"
        logger.info(msg.format(tag, match_ratio, name, image_file))

        # Ask user if partial match is correct
        choice = input("Use this file? y/n/q (default: y): ")
        while choice not in ["n", "y", "", "q"]:
            msg = "Invalid input `{}`, please use `n`, `y`, `q` (default: `y`): "
            choice = input(msg.format(choice))
        logging.debug("Choice: {}".format(choice))
        if choice in "q":
            raise Quit()
        if choice == "n":
            return
    # No Match
    else:
        logger.debug("No match found")
        return

    return image_file


def main(args):
    logger.debug("Args={}".format(args))

    _, extension = os.path.splitext(args.compendium_path)

    if(extension.lower() not in [".zip", ".compendium", ".xml"]):
        msg = "Invalid file format ({}), please provide a `.xml`, `.compendium` or `.zip` file"
        logger.error(msg.format(extension))
        sys.exit(1)

    if not os.path.exists(args.compendium_path):
        msg = "Provided compendium path ({}) does not exist".format(args.compendium_path)
        logger.error(msg)
        sys.exit(1)

    if len(args.image_paths or []) + len(args.token_paths or []) == 0:
        msg = "An image or token directory must be provided"
        logger.error(msg)
        sys.exit(1)

    # Find all image files
    logging.info("Identifying Images")
    images = []
    for image_path in args.image_paths or []:
        images += find_images(image_path)
    tokens = []
    for token_path in args.token_paths or []:
        tokens += find_images(token_path)

    if len(images) + len(tokens) == 0:
        msg = "No images and/or tokens found"
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

            logging.info("Parsing XML")
            tree = ElementTree.parse(xml_path)
            root = tree.getroot()

            logging.info("Searching for Monsters and Items")
            for node in root.findall("*"):
                # Check if this is a compendium entry that supports images
                if node.tag not in ["monster", "item"]:
                    logging.debug("Ignoring `{}` Tag".format(node.tag))
                    continue

                name = node.find("name").text
                logging.debug("Found `{}`: {}".format(node.tag, name))

                # What to search
                tag_files = {}
                if len(images):
                    tag_files["image"] = images
                if node.tag == "monster" and len(tokens):
                    tag_files["token"] = tokens

                for tag, files in tag_files.items():
                    logger.debug("Checking {}".format(tag))
                    # Check if compendium entry already has the tag
                    if node.find(tag) is not None:
                        logging.debug("Already has a `{}`".format(tag))
                        return

                    # Get matching image file
                    image_file_path = match(tag, name, files, args.auto_ratio, args.ask_ratio)

                    # If there is a match add it to the compendium
                    if image_file_path is not None:
                        add_image_to_compendium_zip(image_file_path, node.tag, output_zip)
                        file_name = os.path.basename(image_file_path)
                        ElementTree.SubElement(node, tag).text = file_name

            # Add xml to the output zip
            logging.info("Outputting Compendium")
            output_zip.writestr('compendium.xml', ElementTree.tostring(root))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add images and tokens to Encounter+ compendium '
                                                 'using a fuzzy search algorithm.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('compendium_path', metavar='COMPENDIUM_PATH',
                        help='Path to compendium file, valid formats: .xml, .compendium, .zip')
    parser.add_argument("-i", '--image_path', metavar='IMAGE_PATH', action='append',
                        dest="image_paths",
                        help='Path to image files, valid formats: PNG, JPEG')
    parser.add_argument("-t", '--token_path', metavar='TOKEN_PATH', action='append',
                        dest="token_paths",
                        help='Path to token files, valid formats: PNG, JPEG')

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
    except Quit:
        if os.path.exists(args.output_path):
            logger.debug("Deleting {}".format(args.output_path))
            os.remove(args.output_path)
    except Exception as e:
        logger.exception("Unhandled error occured", exc_info=True)
        if os.path.exists(args.output_path):
            logger.debug("Deleting {}".format(args.output_path))
            os.remove(args.output_path)
