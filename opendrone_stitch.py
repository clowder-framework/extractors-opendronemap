#!/usr/bin/env python
import time
import shutil
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
import gzip
import shutil

from scripts.odm_app import ODMApp

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
from pyclowder.utils import StatusMessage
import pyclowder.files
import pyclowder.datasets

from opendm import context
from opendm.config import alphanumeric_string

# This class prepares and runs the Open Drone Map code in the Clowder environment
class OpenDroneMapStitch(Extractor):

    # Initialization of instance
    def __init__(self, args):
        Extractor.__init__(self)

        # Save a reference to the arguments passed in
        self.opendrone_args = args

        # Add our own touches to the command-line, environment variable parser
        self.parser.add_argument('--denyfiletypes',
                        default=os.getenv('DENYFILETYPES', ""),
                        help='Comma separated list of file extensions (without the period) to never upload')
        self.parser.add_argument('--nofilecompress',
                        default=os.getenv('NOFILECOMPRESS', ""),
                        help='Comma separated list of file extensions (without the period) that will not be compressed before upload')
        self.parser.add_argument('name',
                        metavar='<project name>',
                        type=alphanumeric_string,
                        help='Name of Project (i.e subdirectory of projects folder)')

        # parse command line and load default logging configuration
        self.setup()

        # specify configuration values that are not allowed to be overridden by users
        self.no_override_settings = ["project_path"]

        # Get the file types that may be denied and/or no conpressed. The actual value of the attributes is
        # ignored, just having the attribute existing triggeres the feature
        if len(self.args.denyfiletypes) > 0:
            excludedtypes = self.cleanFileExtensions(self.args.denyfiletypes)
            if 'tif' in excludedtypes:
                self.opendrone_args.noorthophoto = True
            if 'las' in excludedtypes:
                self.opendrone_args.nolas = True
            if 'ply' in excludedtypes:
                self.opendrone_args.noply = True
            if 'csv' in excludedtypes:
                self.opendrone_args.nocsv = True
        if len(self.args.nofilecompress) > 0:
            nocompresstypes =  self.cleanFileExtensions(self.args.nofilecompress)
            if 'las' in nocompresstypes:
                self.opendrone_args.plainlas = True
            if 'ply' in nocompresstypes:
                self.opendrone_args.plainply = True
            if 'csv' in nocompresstypes:
                self.opendrone_args.plaincsv = True

        # setup logging for the exctractor
        logging.getLogger('pyclowder').setLevel(logging.INFO)
        logging.getLogger('__main__').setLevel(logging.DEBUG)
        logging.getLogger('pika').setLevel(logging.INFO)

        # report on some state values
        logging.debug("project_path: %s" % str(self.opendrone_args.project_path))
        logging.debug("name: %s" % str(self.opendrone_args.name))
        logging.debug("rerun_all: %r" % bool(self.opendrone_args.rerun_all))
        logging.debug("excluded file types: %s" % str(self.args.denyfiletypes))

    # Returns an array of comma-separated file types that has been cleaned
    def cleanFileExtensions(self, extensions_string):
        cleanedtypes = extensions_string.split(',')
        for i, ext in enumerate(cleanedtypes):
            cleaned = ext.strip()
            if cleaned.startswith('.'):
                cleaned = cleaned[1:]
            if cleaned.endswith('.'):
                cleaned = cleaned[: cleaned.len()]
            cleanedtypes[i] = cleaned
        return cleanedtypes

    # Main worker method that performs folder maintenance as needed and calls ODM
    def stitch(self, connector, resource):
        logging.debug('Initializing OpenDroneMap app - %s' % system.now())

        # If user asks to rerun everything, delete all of the existing progress directories.
        # TODO: Move this somewhere it's not hard-coded. Alternatively remove everything we don't create
        if self.opendrone_args.rerun_all:
            os.system("rm -rf "
                      + self.opendrone_args.working_project_path + "images_resize/ "
                      + self.opendrone_args.working_project_path + "odm_georeferencing/ "
                      + self.opendrone_args.working_project_path + "odm_meshing/ "
                      + self.opendrone_args.working_project_path + "odm_orthophoto/ "
                      + self.opendrone_args.working_project_path + "odm_texturing/ "
                      + self.opendrone_args.working_project_path + "opensfm/ "
                      + self.opendrone_args.working_project_path + "pmvs/")

        # create an instance of my App BlackBox
        # internally configure all tasks
        connector.status_update(StatusMessage.processing, resource, "Creating ODMApp.")
        app = ODMApp(args=self.opendrone_args)

        # create a plasm that only contains the BlackBox
        connector.status_update(StatusMessage.processing, resource, "Generate Plasm.")
        plasm = ecto.Plasm()
        connector.status_update(StatusMessage.processing, resource, "plasm.insert(app).")
        plasm.insert(app)

        # execute the plasm
        connector.status_update(StatusMessage.processing, resource, "plasm.execute.")
        plasm.execute(niter=1)

        connector.status_update(StatusMessage.processing, resource, "OpenDroneMap app finished.")

        logging.debug('OpenDroneMap app finished - %s' % system.now())

    # Helper function for uploading the file to the calling container with optional compression
    def upload_file(self, file_path, file_name, connector, host, secret_key, dataset_id, compress):
        sourcefile = os.path.join(file_path, file_name)
        if os.path.isfile(sourcefile):
            resultfile = os.path.join(self.opendrone_args.working_project_path, file_name)
            if (compress):
                resultfile = resultfile + ".zip"
                with open(sourcefile, 'rb') as f_in:
                    with gzip.open(resultfile, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                os.rename(sourcefile, resultfile)
            logging.debug("[Finish] upload_to_dataset %s " % resultfile)
            pyclowder.files.upload_to_dataset(connector, host, secret_key, dataset_id, resultfile)
        else:
            raise Exception("%s was not found" % sourcefile)

    # Merges new settings with the master settings. Handles cases when new settings are not permitted
    # to override master settings by restoring those if they've been overridden
    def merge_settings(nastersettings, newsettings):
        mergedsettings = dict()
        mergedsettings.update(nastersettings)
        mergedsettings.update(newsettings)

        # Don't allow the override of certain settings
        for i, name in enumerate(self.no_override_settings):
            if hasattr(newsettings, name):
                mergedsettings[name] = mastersettings[name]

        return mergedsettings

    # Overidden method that checks if we want to process a message, or not
    def check_message(self, connector, host, secret_key, resource, parameters):
        if resource['triggering_file'] == "extractors-opendronemap.txt" or resource['triggering_file'] is None:
            logging.debug("extractors-opendronemap.txt file uploaded")
            return CheckMessage.download
        return CheckMessage.ignore

    # Overridden method that performs the processing on the message
    # Prepares the environment for Open Drone Map by linking to image files and
    # checking settings for overrides. Also uploads the results of the run
    def process_message(self, connector, host, secret_key, resource, parameters):
        starttime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        logging.debug("Started computing images at %s" % str(starttime))
        start_time = time.time()

        # We store the settings here in case they're
        # modified by the caller and we restore them when we're all done
        original_settings = self.opendrone_args

        try:
            paths = list()
            configfilename = "";
            for localfile in resource['local_paths']:
                # deal with mounted/local files
                if localfile.lower().endswith('.jpg'):
                    paths.append(localfile)
                elif localfile.lower().endswith("extractors-opendronemap.txt"):
                    configfilename = localfile
                else:
                    # deal with downloaded files
                    for image in resource['files']:
                        if image['filepath'] == localfile:
                            if image['filename'].lower().endswith('.jpg'):
                                paths.append(image['filename'])
                            elif image['filename'].lower().endswith("extractors-opendronemap.txt"):
                                configfilename = image['filename']

            # Check for option overrides
            if configfilename != "" and os.stat(configfilename).st_size > 0:
                configfile = os.open(configfilename)
                if configfile:
                    newsettings = yaml.safe_load(configfile)
                    if newsettings:
                        # Use the merged settings for this run
                        self.opendrone_args = self.merge_settings(self.opendrone_args, newsettings)

            # creating the folder to place the links to image files. Open Drone Maps wants all
            # the source image files in one folder
            self.opendrone_args.working_project_path = io.join_paths(self.opendrone_args.project_path, self.opendrone_args.name)
            imagesfolder = os.path.join(self.opendrone_args.working_working_project_path, "images")
            if not io.dir_exists(imagesfolder):
                logging.debug('Directory %s does not exist. Creating it now.' % imagesfolder)
                system.mkdir_p(os.path.abspath(imagesfolder))
                logging.debug('[Prepare] create images folder: %s' % imagesfolder)

            # symlink input images files to imagesfolder
            for input in paths:
                source = os.path.join(imagesfolder, os.path.basename(input))
                os.symlink(input, source)
                logging.debug("[Prepare] image symlink: %s" % source)

            # perform the drone processing
            self.stitch(connector, resource)

            # Upload the output files to the dataset, compressing the larger files
            if not hasattr(self.opendrone_args, "noorthophoto"):
                path = os.path.join(self.opendrone_args.working_project_path, "odm_orthophoto")
                self.upload_file(path, "odm_orthophoto.tif", connector, host, secret_key, resource['id'], false)

            path = os.path.join(self.opendrone_args.working_project_path, "odm_georeferencing")
            if not hasattr(self.opendrone_args, "nolas"):
                self.upload_file(path, "odm_georeferencing.las", connector, host, secret_key, resource['id'], true & (not hasattr(self.opendrone_args, "plainlas")))
            if not hasattr(self.opendrone_args, "noply"):
                self.upload_file(path, "odm_georeferencing.ply", connector, host, secret_key, resource['id'], true & (not hasattr(self.opendrone_args, "plainply")))
            if not hasattr(self.opendrone_args, "nocsv"):
                self.upload_file(path, "odm_georeferencing.csv", connector, host, secret_key, resource['id'], true & (not hasattr(self.opendrone_args, "plaincsv")))

            endtime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            logging.debug("[Finish] complete computing images at %s" % str(endtime))
            logging.debug("Elapse time: " + str((time.time() - start_time)/60) + " minutes")
        except Exception as ex:
            logging.debug(ex.message)
        finally:
            # Restore any settings that might have changed
            self.opendrone_args = original_settings;

            try:
                # Clean up the working environment by removing links and created folders
                logging.debug("[Cleanup] remove computing folder: %s" % self.opendrone_args.working_project_path)
                for path in paths:
                    inputfile = os.path.basename(path)
                    odmfile = os.path.join("/tmp", inputfile+".jpg")
                    if os.path.isfile(odmfile):
                        logging.debug("[Cleanup] remove odm .jpg: %s" % odmfile)
                        os.remove(odmfile)
                shutil.rmtree(self.opendrone_args.working_project_path)
            except OSError:
                pass

if __name__ == "__main__":
    args = config.config()
    args.project_path = tempfile.mkdtemp()
    extractor = OpenDroneMapStitch(args)
    extractor.start()
