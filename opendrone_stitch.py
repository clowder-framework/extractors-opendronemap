#!/usr/bin/env python
import time
import shutil
import datetime
import logging
import tempfile
import os
import re
import json
import subprocess
import gzip
import yaml

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
from pyclowder.utils import StatusMessage
import pyclowder.files
import pyclowder.datasets

from opendm import config
from opendm import system
from opendm import io

# This class prepares and runs the Open Drone Map code in the Clowder environment
class OpenDroneMapStitch(Extractor):

    # Initialization of instance
    def __init__(self):
        super(OpenDroneMapStitch, self).__init__()

        # Add our own touches to the command-line, environment variable parser
        # Used to assist in debugging a running instance
        self.parser.add_argument('--waitonerror',
                                 default=False,
                                 help='Wait around if an error ocurrs and don\'t prcess other requests (used for debugging)')

        # specify configuration values that are not allowed to be overridden by users
        self.no_override_settings = ["project_path"]

        self.opendrone_args = None

    # parse command line and load default logging configuration
    def dosetup(self, args):

        # Save a reference to the arguments passed in
        self.opendrone_args = args
        self.opendrone_args.name = "clowder"

        super(OpenDroneMapStitch, self).setup()

        # setup logging for the extractor
        self.logger = logging.getLogger('__main__')
        self.logger.setLevel(logging.INFO)
        logging.getLogger('pyclowder').setLevel(logging.INFO)
        logging.getLogger('pika').setLevel(logging.INFO)

        # report on some state values
        self.logger.debug("project_path: %s" % str(self.opendrone_args.project_path))
        self.logger.debug("name: %s" % str(self.opendrone_args.name))
        self.logger.debug("rerun_all: %r" % bool(self.opendrone_args.rerun_all))

    # Returns an array of comma-separated file types that has been cleaned
    def clean_file_extensions(self, extensions_string):
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
        self.logger.debug('Initializing OpenDroneMap app - %s' % system.now())

        # If user asks to rerun everything, delete all of the existing progress directories.
        # TODO: Move this somewhere it's not hard-coded. Alternatively remove everything
        # we don't create
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

        settingsfilepath = os.path.join(self.opendrone_args.project_path, "settings.yaml")
        with open(settingsfilepath, 'w') as out_f:
            odm_args = vars(self.opendrone_args)
            for key in odm_args:
                if not odm_args[key] is None:
                    out_f.write(str(key) + " : " + str(odm_args[key]) + "\n")

        proc = None
        try:
            my_env = os.environ.copy()
            my_env["ODM_SETTINGS"] = settingsfilepath
            my_path = os.path.dirname(os.path.realpath(__file__))
            if not my_path:
                my_path = "."
            script_path = os.path.join(my_path,"worker.py")
            proc = subprocess.Popen([script_path, "code"], bufsize=-1, env=my_env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding="UTF-8")
        except Exception as ex:
            connector.status_update(StatusMessage.processing, resource, "Exception: " + str(ex))
            self.logger.exception("Error running process.")

        logfilepath = os.path.join(self.opendrone_args.project_path, "odm_stitching.log")
        with open(logfilepath, 'wb', 0) as logfile:
            if proc:
                # Loop here processing the output until the proc finishes
                self.logger.debug("Waiting for process to finish")
                connector.status_update(StatusMessage.processing, resource, "Waiting for process to finish")
                while proc.returncode is None:
                    if not proc.stdout is None:
                        try:
                            while True:
                                line = proc.stdout.readline()
                                if line:
                                    logfile.write(line.encode('utf-8'))
                                    line = line.rstrip('\n')
                                    if "[ERROR]" in line:
                                        connector.status_update(StatusMessage.processing, resource, line.replace("[ERROR] ", ""))
                                        line = line.replace("[ERROR] ", "")
                                        self.logger.error(line)
                                    elif " ERROR: " in line:
                                        connector.status_update(StatusMessage.processing, resource, re.sub(r".* ERROR: ", "ERROR: ", line))
                                        line = re.sub(r".* ERROR: ", "ERROR: ", line)
                                        self.logger.error(line)
                                    elif "[WARNING]" in line:
                                        line = line.replace("[WARNING] ", "")
                                        self.logger.warning(line)
                                    elif " WARNING: " in line:
                                        line = re.sub(r".* WARNING: ", "", line)
                                        self.logger.warning(line)
                                    elif "[INFO]" in line:
                                        line = line.replace("[INFO] ", "")
                                        self.logger.info(line)
                                    elif " INFO: " in line:
                                        line = re.sub(r".* INFO: ", "", line)
                                        self.logger.info(line)
                                    else:
                                        self.logger.debug(line)
                                else:
                                    proc.poll()
                                    break
                        except Exception as ex:
                            self.logger.exception("Error reading line.")
                            connector.status_update(StatusMessage.processing, resource, "Ignoring exception while waiting: " + str(ex))
    
                    # Sleep and try again for process to complete
                    time.sleep(1)
                self.logger.debug("Return code: " + str(proc.returncode))
                connector.status_update(StatusMessage.processing, resource, "Return code: " + str(proc.returncode))
    
            connector.status_update(StatusMessage.processing, resource, "OpenDroneMap app finished.")
    
        self.logger.debug('OpenDroneMap app finished - %s' % system.now())
        return

    # Helper function for uploading the file to the calling container with optional compression
    def upload_file(self, source_file_name, dest_file_name, connector, host, secret_key, resource, compress):
        sourcefile = os.path.join(self.opendrone_args.project_path, source_file_name)
        if os.path.isfile(sourcefile):
            resultfile = os.path.join(self.opendrone_args.project_path, dest_file_name)
            if compress:
                resultfile = resultfile + ".zip"
                with open(sourcefile, 'rb') as f_in:
                    with gzip.open(resultfile, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                os.rename(sourcefile, resultfile)
            self.logger.debug("[Finish] upload_to_dataset %s " % resultfile)
            pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'], resultfile)
        else:
            connector.status_update(StatusMessage.processing, resource, "Could not upload %s" % source_file_name)
            self.logger.error("%s was not found, might not have been generated" % source_file_name)

    # Merges new settings with the master settings. Handles cases when new settings are not permitted
    # to override master settings by restoring those if they've been overridden
    def merge_settings(self, mastersettings, newsettings):
        self.logger.debug('Merging settings: ' + str(newsettings))
        for name in newsettings:
            if not name in self.no_override_settings:
                setattr(mastersettings, name, newsettings[name])

        return mastersettings

    # Overidden method that checks if we want to process a message, or not
    def check_message(self, connector, host, secret_key, resource, parameters):
        if resource['triggering_file'] == "extractors-opendronemap.txt" or resource['triggering_file'] is None:
            self.logger.debug("extractors-opendronemap.txt file uploaded")
            return CheckMessage.download
        return CheckMessage.ignore

    # Overridden method that performs the processing on the message
    # Prepares the environment for Open Drone Map by linking to image files and
    # checking settings for overrides. Also uploads the results of the run
    def process_message(self, connector, host, secret_key, resource, parameters):
        starttime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        self.logger.debug("Started computing images at %s" % str(starttime))
        start_time = time.time()

        # We store the settings here in case they're
        # modified by the caller and we restore them when we're all done
        original_settings = self.opendrone_args
        original_project_path = self.opendrone_args.project_path

        paths = list()
        configfilename = ""
        try:
            for localfile in resource['local_paths']:
                # deal with mounted/local files
                if localfile.lower().endswith('.jpg'):
                    paths.append(localfile)
                elif localfile.lower().endswith("extractors-opendronemap.txt"):
                    configfilename = localfile
                else:
                    # deal with downloaded files
                    for image in resource['files']:
                        if 'filepath' in image and image['filepath'] == localfile:
                            if image['filename'].lower().endswith('.jpg'):
                                paths.append(image['filename'])
                            elif image['filename'].lower().endswith("extractors-opendronemap.txt"):
                                configfilename = image['filename']

            # Check for option overrides
            if configfilename != "" and os.stat(configfilename).st_size > 0:
                configfile = open(configfilename, "r")
                if configfile:
                    newsettings = yaml.safe_load(configfile)
                    if newsettings:
                        # Use the merged settings for this run
                        self.opendrone_args = self.merge_settings(self.opendrone_args, newsettings)
        
            override_settings = json.loads(parameters['parameters'])
            if override_settings:
                self.logger.debug('Overriding settings: ' + str(override_settings))
                self.opendrone_args = self.merge_settings(self.opendrone_args, override_settings)

            # creating the folder to place the links to image files. Open Drone Maps wants all
            # the source image files in one folder
            self.opendrone_args.project_path = io.join_paths(self.opendrone_args.project_path, self.opendrone_args.name)
            imagesfolder = os.path.join(self.opendrone_args.project_path, "images")
            if not io.dir_exists(imagesfolder):
                self.logger.debug('Directory %s does not exist. Creating it now.' % imagesfolder)
                system.mkdir_p(os.path.abspath(imagesfolder))
                self.logger.debug('[Prepare] create images folder: %s' % imagesfolder)

            # symlink input images files to imagesfolder
            for input in paths:
                source = os.path.join(imagesfolder, os.path.basename(input))
                os.symlink(input, source)
                self.logger.debug("[Prepare] image symlink: %s" % source)

            # perform the drone processing and preserve log output in a file
            self.stitch(connector, resource)

            # Upload the logfile from the stitching operation to the dataset
            if not "upload_logfile" in self.opendrone_args or self.opendrone_args.upload_logfile:
                self.upload_file("odm_stitching.log", "odm_stitching.log", connector, host, secret_key, resource, False)

            # Upload the output files to the dataset, optionally compressing the larger files
            if not self.opendrone_args.skip_orthophoto:
                self.upload_file("odm_orthophoto/odm_orthophoto.tif", "odm_orthophoto.tif", connector, host, secret_key, resource, False)

            # upload LAZ file
            if not "upload_laz" in self.opendrone_args or self.opendrone_args.upload_laz:
                self.upload_file("odm_georeferencing/odm_georeferenced_model.laz", "odm_georeferenced_model.laz", connector, host, secret_key, resource, False)

            # upload dem/dsm/dtpm
            if self.opendrone_args.dsm:
                self.upload_file("odm_dem/dsm.tif", "dsm.tif", connector, host, secret_key, resource, False)
            if self.opendrone_args.dtm:
                self.upload_file("odm_dem/dtm.tif", "dtm.tif", connector, host, secret_key, resource, False)

            # upload boundary/projection files
            if not "upload_boundary" in self.opendrone_args or self.opendrone_args.upload_boundary:
                self.upload_file("odm_georeferencing/proj.txt", "odm_georeferenced_model.bounds.proj.txt", connector, host, secret_key, resource, False)
                self.upload_file("odm_georeferencing/odm_georeferenced_model.bounds.geojson", "odm_georeferenced_model.geojson", connector, host, secret_key, resource, False)
                self.upload_file("odm_georeferencing/odm_georeferenced_model.boundary.json", "odm_georeferenced_model.json", connector, host, secret_key, resource, False)

            # all done
            endtime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            self.logger.debug("[Finish] complete computing images at %s" % str(endtime))
            self.logger.debug("Elapse time: " + str((time.time() - start_time)/60) + " minutes")
        except:
            self.logger.exception("Could not stich image.")
        finally:
            # Restore any settings that might have changed
            self.opendrone_args = original_settings

            try:
                # Clean up the working environment by removing links and created folders
                self.logger.debug("[Cleanup] remove computing folder: %s" % self.opendrone_args.project_path)
                for path in paths:
                    inputfile = os.path.basename(path)
                    odmfile = os.path.join("/tmp", inputfile+".jpg")
                    if os.path.isfile(odmfile):
                        self.logger.debug("[Cleanup] remove odm .jpg: %s" % odmfile)
                        os.remove(odmfile)
                shutil.rmtree(self.opendrone_args.project_path)
            except OSError:
                pass
            finally:
                self.opendrone_args.project_path = original_project_path


if __name__ == "__main__":
    args = config.config()
    args.project_path = tempfile.mkdtemp()

    extractor = OpenDroneMapStitch()
    extractor.dosetup(args)
    extractor.start()
