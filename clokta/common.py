'''
Simple utility methods for the module
'''
import logging
import sys
from datetime import date, datetime

import click


class Common(object):

    quiet_out = 0
    brief_out = 1
    long_out = 2
    debugging_out=3
    output_format=brief_out

    ''' Console printing helpers '''

    @classmethod
    def get_output_format(cls):
        return Common.output_format

    @classmethod
    def set_output_format(cls, new_format):
        Common.output_format=new_format

    @classmethod
    def is_debug(cls):
        return Common.output_format == Common.debugging_out

    @classmethod
    def to_std_error(cls):
        return Common.output_format == Common.quiet_out

    @classmethod
    def dump_err(cls, message, exit_code):
        ''' Dump error to console and exit program '''
        if Common.is_debug():
            logging.exception(message)
        click.secho(message=message, bold=True, fg='red', err=True)
        sys.exit(exit_code)

    @classmethod
    def dump_out(cls, message, new_line=True, bold=False):
        ''' Dump verbose message to console '''
        click.secho(message, nl=new_line, bold=bold, fg='blue', err=Common.to_std_error())

    @classmethod
    def echo(cls, message, new_line=True, bold=False, always_stdout=False):
        ''' Dump standard message to console '''
        to_std_error = not always_stdout and Common.to_std_error()
        click.secho(message, nl=new_line, bold=bold, err=to_std_error)

    @classmethod
    def json_serial(cls, obj):
        ''' JSON serializer for objects not serializable by default json code '''
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))
