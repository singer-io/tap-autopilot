#!/usr/bin/env python

from setuptools import setup

setup(name='tap-autopilot',
      version='0.2.0',
      description='Singer.io tap for extracting data from the Autopilot API',
      author='Stitch',
      author_email='support@stitchdata.com',
      url='http://singer.io',
      classifiers=['Programming Language :: Python :: 3 :: Only'],
      py_modules=['tap_autopilot'],
      install_requires=[
          'attrs==16.3.0',
          'singer-python==5.8.1',
          'requests==2.20.0',
          'backoff==1.8.0',
          'pendulum==1.2.0'
      ],
      extras_require={
          'dev': [
              'pylint',
              'ipdb',
              'nose',
          ]
      },
      entry_points='''
          [console_scripts]
          tap-autopilot=tap_autopilot:main
      ''',
      packages=['tap_autopilot'],
      package_data={
          'tap_autopilot/schemas': ["*.json"]
      },
      include_package_data=True,
     )
