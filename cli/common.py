'''
Simple utility methods for the module
'''
import logging
import sys
from datetime import date, datetime

import click


class Common(object):
    ''' Console printing helpers '''

    @classmethod
    def dump_err(cls, message, exit_code, verbose=False):
        ''' Dump error to console and exit program '''
        if verbose:
            logging.exception(message)
        click.secho(message, bold=True, fg='red')
        sys.exit(exit_code)

    @classmethod
    def dump_verbose(cls, message, new_line=True, bold=False):
        ''' Dump verbose message to console '''
        click.secho(message, nl=new_line, bold=bold, fg='blue')

    @classmethod
    def echo(cls, message, new_line=True, bold=False):
        ''' Dump standard message to console '''
        click.secho(message, nl=new_line, bold=bold)

    @classmethod
    def json_serial(cls, obj):
        ''' JSON serializer for objects not serializable by default json code '''
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))
