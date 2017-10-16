#!/usr/bin/env python

import datetime
import logging
import tempfile
import math
import os
import subprocess

from opendm import log
from opendm import config
from opendm import system
from opendm import io

import ecto
import os
import sys

from scripts.odm_app import ODMApp

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
from pyclowder.utils import StatusMessage
import pyclowder.files
import pyclowder.datasets

from opendm import context
from opendm.config import alphanumeric_string


class OpenDroneMapStitch(Extractor):

    def __init__(self, args):
        Extractor.__init__(self)
        self.opendrone_args = args

        self.parser.add_argument('name',
                        metavar='<project name>',
                        type=alphanumeric_string,
                        help='Name of Project (i.e subdirectory of projects folder)')
        # parse command line and load default logging configuration
        self.setup()

        # setup logging for the exctractor
        logging.getLogger('pyclowder').setLevel(logging.INFO)
        logging.getLogger('__main__').setLevel(logging.DEBUG)
        logging.getLogger('pika').setLevel(logging.INFO)

        logging.debug("project_path: %s" % str(self.opendrone_args.project_path))
        logging.debug("name: %s" % str(self.opendrone_args.name))
        logging.debug("rerun_all: %r" % bool(self.opendrone_args.rerun_all))

    def stitch(self, connector, resource):
        logging.debug('Initializing OpenDroneMap app - %s' % system.now())

        # If user asks to return everything, delete all of the existing progress directories.
        # TODO: Move this somewhere it's not hard-coded
        if self.opendrone_args.rerun_all:
            os.system("rm -rf "
                      + self.opendrone_args.project_path + "images_resize/ "
                      + self.opendrone_args.project_path + "odm_georeferencing/ "
                      + self.opendrone_args.project_path + "odm_meshing/ "
                      + self.opendrone_args.project_path + "odm_orthophoto/ "
                      + self.opendrone_args.project_path + "odm_texturing/ "
                      + self.opendrone_args.project_path + "opensfm/ "
                      + self.opendrone_args.project_path + "pmvs/")
        # create an instance of my App BlackBox
        # internally configure all tasks
        connector.status_update(StatusMessage.processing, resource, "Creating ODMApp.")
        app = ODMApp(args=self.opendrone_args)

        connector.status_update(StatusMessage.processing, resource, "Generate Plasm.")
        # create a plasm that only contains the BlackBox
        plasm = ecto.Plasm()
        connector.status_update(StatusMessage.processing, resource, "plasm.insert(app).")
        plasm.insert(app)

        # execute the plasm
        connector.status_update(StatusMessage.processing, resource, "plasm.execute.")
        plasm.execute(niter=1)

        connector.status_update(StatusMessage.processing, resource, "OpenDroneMap app finished.")

        logging.debug('OpenDroneMap app finished - %s' % system.now())

    def check_message(self, connector, host, secret_key, resource, parameters):
        if resource['triggering_file'] == "stitch.txt" or resource['triggering_file'] is None:
            logging.debug("stitch.txt file uploaded")
            return CheckMessage.download
        return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        starttime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        logging.debug("Started computing images at %s" % str(starttime))

        try:
            paths = list()
            for localfile in resource['local_paths']:
                # deal with mounted/local files
                if localfile.lower().endswith('.jpg'):
                    paths.append(localfile)
                else:
                    # deal with downloaded files
                    for image in resource['files']:
                        if image['filepath'] == localfile and image['filename'].lower().endswith('.jpg'):
                            paths.append(image['filename'])

            self.opendrone_args.project_path = io.join_paths(self.opendrone_args.project_path, self.opendrone_args.name)
            imagesfolder = os.path.join(self.opendrone_args.project_path, "images")
            if not io.dir_exists(imagesfolder):
                logging.debug('Directory %s does not exist. Creating it now.' % imagesfolder)
                system.mkdir_p(os.path.abspath(imagesfolder))
                logging.debug('create images folder: %s' % imagesfolder)

            # symlink input images files to imagesfolder
            for input in paths:
                source = os.path.join(imagesfolder, os.path.basename(input))
                os.symlink(input, source)
                logging.debug("image symlink: %s" % source)
            # run opendronemap
            self.stitch(connector, resource)

            # create a temp folder to hold the result files.
            # folder = tempfile.mkdtemp()

            endtime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        except Exception as ex:
            logger.debug(ex.message)
        finally:
            try:
                
                #os.remove(sectionfile)
            except OSError:
                pass

        logging.debug("Finished computing images at %s" % str(endtime))

if __name__ == "__main__":
    args = config.config()
    extractor = OpenDroneMapStitch(args)
    extractor.start()