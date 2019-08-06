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
        """
        :return: whether to output debugging information
        :rtype: bool
        """
        return Common.output_format == Common.debugging_out

    @classmethod
    def to_std_error(cls):
        """
        :return: whether clokta is running in a special mode for piping unix commands where most normal output is actually
        sent to stderr and only executable statements are output to stdout
        :rtype: bool
        """
        return Common.output_format == Common.quiet_out

    @classmethod
    def dump_err(cls, message, new_line=True):
        """
        Print error information to the user
        :param message: the message to print
        :param new_line: whether to put a new line at the end (default is include new line)
        """
        click.secho(message=message, nl=new_line, bold=True, fg='red', err=True)

    @classmethod
    def dump_out(cls, message, new_line=True):
        """
        Print debug information to the user
        :param message: the message to print
        :param new_line: whether to put a new line at the end (default is include new line)
        """
        if new_line:
            message += '\n'
        if Common.is_debug():
            click.secho(message=message, nl=new_line, bold=False, fg='blue', err=Common.to_std_error())

    @classmethod
    def echo(cls, message, new_line=True, bold=False, always_stdout=False):
        """
        Print message to user.  This is meant for info level messages and prompts for information
        :param message: message to print
        :param new_line: whether to put a new line at the end (default is include new line)
        :param bold: whether to make the text bold
        :param always_stdout: sometimes users will pipe the output of clokta to another shell script and
        all prompting and info messages should be sent to stderr and only executable commands should be sent to
        stdout.  always_stdout should be True if this output is an executable command that should go to stdout then
        """
        to_std_error = not always_stdout and Common.to_std_error()
        click.secho(message, nl=new_line, bold=bold, err=to_std_error)

    @classmethod
    def json_serial(cls, obj):
        ''' JSON serializer for objects not serializable by default json code '''
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))
