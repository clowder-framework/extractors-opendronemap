Extractor to stitch drone images
=================================================

This is a Clowder extractor to stitch drone images into one image using OpenDroneMap.

## Build
```
docker build -t clowder/extractors-opendronemap .
```
## How to Run - Quick Start
Suggested allocation is of 10GB memory for docker to run the extractor.

1. Start the docker container
```
docker run --name=opendronemap-py2 -d --restart=always -e 'RABBITMQ_URI=amqp://user1:pass1@rabbitmq.ncsa.illinois.edu:5672/clowder-dev' -e 'RABBITMQ_EXCHANGE=clowder' -e 'TZ=/usr/share/zoneinfo/US/Central' -e 'REGISTRATION_ENDPOINTS=http://clowderhostname:9000/api/extractors?key=key1' clowder/extractors-opendronemap
```

2. Create an empty extractors-opendronemap.txt file to run with the default parameters.

3. Login clowder and create dataset. And then upload images into dataset. Finally, upload extractors-opendronemap.txt to trigger opendronemap extractor to do stitching.

4. Upon completion, .tif, .las, .ply, and .csv files will be shown in the dataset.
Note that the point cloud files may be compressed and have the compression extension added to their file names.
For example, a compressed .las file will actually have an extension of .las.zip.
Also, if the docker container has been configured to not upload one or more of these files, they won't be available.

## How to Run - Advanced version

Suggested allocation is of 10GB memory for docker to run the extractor.

### 1. Start the docker container

There are two environment variables named `DENYFILETYPES` and `NOFILECOMPRESS` that can be set when starting the docker container which affect what data is allowed to be uploaded to Clowder.

The extractors-opendronemap.txt file used to start processing may contain overrides of these two environment variables.
In the case of DENYFILETYPES, the overrides only prevent additional, presumeably unwanted, files from being uploaded.
In the case of NOFILECOMPRESS, the compression step will be skipped and the uncompressed, much larger, file will be uploaded.
More information on these variables is below.

To specify these variables on container startup, use the `-e` command line option to define them.
An example of this is `-e 'DENYFILETYPES=ply,csv'` which prevents the odm_georeferencing.ply and odm_georeferencing.ply files from uploading.

The command to start the docker container could then be modified to look like the following.
```
docker run --name=opendronemap-py2 -d --restart=always -e 'DENYFILETYPES=ply,csv' -e 'RABBITMQ_URI=amqp://user1:pass1@rabbitmq.ncsa.illinois.edu:5672/clowder-dev' -e 'RABBITMQ_EXCHANGE=clowder' -e 'TZ=/usr/share/zoneinfo/US/Central' -e 'REGISTRATION_ENDPOINTS=http://clowderhostname:9000/api/extractors?key=key1' clowder/extractors-opendronemap
```

#### DENYFILETYPES
By default all ODM generated files of these types are uploaded into Clowder.
The purpose of this variable is to prevent files of certain types from being uploaded for as long as the container is running (including auto restart).
The variable, when defined, contains a comma-separated list of file extensions.
The valid extensions that will prevent files from being uploaded are:
* tif - orthomosaic image
* las - point cloud
* csv - point cloud
* ply - point cloud

#### NOFILECOMPRESS
By default the point-cloud related files are compressed before they are uploaded into Clowder.
The purpose of this variable is to specify files that should never be compressed before their upload.
The variable, when defined, contains a comma-separated list of file extensions.
The valid extensions that will prevent files from being compressed are:
* las - point cloud
* csv - point cloud
* ply - point cloud

### 2. Create extractors-opendronemap.txt file

Creating an empty extractors-opendronemap.txt file will produce the default results that the OpenDroneMap docker extractor instance is configured as.

To override, or fine tune, the default behavior, copy the 'extractors-opendronemap.txt.sample' file to 'extractors-opendronemap.txt' and modify the contents.
The extractors-opendronemap.txt.sample file is a modified version of the extractors-opendronemap [configuration file](https://opensource.ncsa.illinois.edu/bitbucket/projects/CATS/repos/extractors-opendronemap/browse/settings.yaml) and has fewer options.
The removed options are ones that could negatively impact the running of the docker container and are ignored even if they are added back to the extractors-opendronemap.txt file.

### 3. Create dataset and upload files

This step is the same as the one in the Quick Start section above.

### 4. Files will be shown in the dataset

Depending upon how the extractor-opendronemap container was started, and which options may have been set in the extractors-opendronemap.txt file, the results will show up in the dataset once the OpenDroneMap job is completed
