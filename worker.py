#!/usr/bin/env python

import os
import sys
import json
import yaml
import ecto

from opendm import config

from scripts.odm_app import ODMApp

print "[worker] Starting"

arg_file = os.environ.get('ODM_SETTINGS')

print "[worker] settings file: " + arg_file

if arg_file is None:
    print "[worker] raising missing argument"
    raise ValueError("Missing settings file environment variable")

newsettings = None
print "[worker] loading settings"
with open(arg_file) as in_f:
    newsettings = yaml.safe_load(in_f)

if not newsettings:
    print "[worker] bad argument file"
    raise ValueError("Invalid argument file passed in")

print "[worker] getting config"
args = config.config()

print "[worker] merging config"
for name in newsettings:
    setattr(args, name, newsettings[name])

print "[worker] Starting"
app = ODMApp(args=args)

# create a plasm that only contains the BlackBox
plasm = ecto.Plasm()
plasm.insert(app)

# execute the plasm
plasm.execute(niter=1)

print "[worker] finishing"
