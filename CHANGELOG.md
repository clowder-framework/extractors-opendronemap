# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).


## 2.2.0 - 2022-08-22

### Added
- Can now create DSM/DTM images
- Can now pick what to upload
- docker-compose file for testing of opendronemap

### Changed
- Updated base image to opendronemap 2.8.8

### Removed
- fast_orto is no longer supported, this seemed to fail a lot.
- ability to upload shapefiles since these were not generated
