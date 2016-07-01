# -*- coding:utf-8 -*-
import os
import re
import sublime, sublime_plugin


class SoftuneOpener():
    def __init__(self):
        self.args = list()
        self.args.append('-D__io=')
        self.args.append('-D__direct=')
        self.args.append('-D__CPU_MB95F718L__')
        self.args.append('-D__IO_FAR')
        self.args.append('-D__far=')
        self.args.append('-D__EI()={}')
        self.args.append('-D__DI()={}')
        self.args.append('-D__set_il(x)={}')
        self.args.append('-D__wait_nop()={}')
        self.args.append('-D__asm(x)={}')
        self.args.append('-D__interrupt=')
        self.sys_inc = list()

    @staticmethod
    def can_open(filename):
        return os.path.splitext(filename)[1].lower() == '.prj'

    def open(self, project_file, view):
        file_content = open(project_file).read()
        file_content = file_content.split('[MEMBER-Debug]')[0]
        self.workpath = os.path.dirname(project_file)

        self.c_files = list()
        for f in re.findall(r'F\d+=\d+\s*c\s*(.+)', file_content, re.I):
            f = f.replace('\\', os.sep)
            f = os.path.normpath(os.path.join(self.workpath, f))
            self.c_files.append(f)

        file_content = open(project_file[:-3] + 'dat').read()
        self.usr_inc = list()
        for inc in re.findall(r'\-I "(.*)"', file_content, re.I):
            inc = inc.replace('\\', os.sep)
            self.usr_inc.append(inc)
            print(inc)
        arg_dict = dict()
        arg_dict['workpath'] = self.workpath
        arg_dict['sys_inc'] = self.sys_inc
        arg_dict['usr_inc'] = self.usr_inc
        arg_dict['c_files'] = self.c_files
        arg_dict['args'] = self.args
        view.window().run_command('sclang_open', {'opener': arg_dict})

class IAROpener():
    def __init__(self):
        self.args = list()
        # self.args.append(r'-IC:\Program Files\IAR Systems\Embedded Workbench 6.4\arm\CMSIS\Include')
        self.sys_inc = [
                r'C:\Program Files\IAR Systems\Embedded Workbench 6.4\arm\inc\c',
                r'C:\Program Files\IAR Systems\Embedded Workbench 6.4\arm\CMSIS\Include']

    @staticmethod
    def can_open(filename):
        return os.path.splitext(filename)[1].lower() == '.eww'

    def open(self, project_file, view):
        import xml.etree.cElementTree as et
        tree = et.ElementTree(file=project_file)
        self.workpath = os.path.dirname(project_file)
        ewpfile = tree.iterfind('project/path', tree.getroot()).__next__().text
        ewpfile = ewpfile.replace('$WS_DIR$', self.workpath)
        tree = et.ElementTree(file=ewpfile)
        self.usr_inc = list()
        for f in tree.iterfind('configuration/settings[name="ICCARM"]/data/option[name="CCIncludePath2"]/state'):
            fp = f.text.replace('$PROJ_DIR$', self.workpath)
            fp = os.path.normpath(fp)
            fp = os.path.normcase(fp)
            self.usr_inc.append(fp.replace('\\', os.sep))
        self.c_files = list()
        for f in tree.iterfind('group/file/name'):
            if f.text.split('.')[-1].lower() in ['c', 'cpp']:
                fp = f.text.replace('$PROJ_DIR$', self.workpath)
                fp = os.path.normpath(fp)
                fp = os.path.normcase(fp)
                self.c_files.append(fp)
        for f in tree.iterfind('group/group/file/name'):
            if f.text.split('.')[-1].lower() in ['c', 'cpp']:
                fp = f.text.replace('$PROJ_DIR$', self.workpath)
                fp = os.path.normpath(fp)
                fp = os.path.normcase(fp)
                self.c_files.append(fp)

        arg_dict = dict()
        arg_dict['workpath'] = self.workpath
        arg_dict['sys_inc'] = self.sys_inc
        arg_dict['usr_inc'] = self.usr_inc
        arg_dict['c_files'] = self.c_files
        arg_dict['args'] = self.args
        view.window().run_command('sclang_open', {'opener': arg_dict})

class CubesuiteOpener():
    def __init__(self):
        self.args = [
            '-DNOP()=',
            '-DDI()=',
            '-DEI()=',
            '-D__interrupt=',
            '-Dbit=char',
            '-Dboolean=char',
            '-Dcallf=',
            '-Dcallt=',
            '-D__callf=',
            '-D__callt=',
            '-Ddivuw(a, b)=((int)0)',
            '-Dwtobcd(x)=((int)0)',
            '-Dsreg=',
            '-Dleaf=',
            '-D__leaf='
        ]
        self.sys_inc = list()

    @staticmethod
    def can_open(filename):
        return os.path.splitext(filename)[1].lower() == '.mtpj'

    def open(self, project_file, view):
        import xml.etree.cElementTree as et
        tree = et.ElementTree(file=project_file)
        self.workpath = os.path.dirname(project_file)
        self.usr_inc = list()
        f = tree.iterfind('./Class/Instance/AdditionalIncludePaths-0').__next__()
        fp = os.path.join(self.workpath, f.text)
        fp = fp.strip()
        fp = os.path.normpath(fp)
        fp = os.path.normcase(fp)
        fp = fp.replace('\\', os.sep)
        self.usr_inc.append(fp)
        self.c_files = list()
        for f in tree.iterfind('./Class/Instance[Type="File"]/RelativePath'):
            fp = os.path.join(self.workpath, f.text)
            fp = os.path.normpath(fp)
            fp = os.path.normcase(fp)
            fp = fp.replace('\\', os.sep)
            if os.path.splitext(fp)[1].lower() == '.c':
                self.c_files.append(fp)

        arg_dict = dict()
        arg_dict['workpath'] = self.workpath
        arg_dict['sys_inc'] = self.sys_inc
        arg_dict['usr_inc'] = self.usr_inc
        arg_dict['c_files'] = self.c_files
        arg_dict['args'] = self.args
        view.window().run_command('sclang_open', {'opener': arg_dict})


class Opener():
    @staticmethod
    def get_opener(filename):
        if SoftuneOpener.can_open(filename):
            return SoftuneOpener()
        if IAROpener.can_open(filename):
            return IAROpener()
        if CubesuiteOpener.can_open(filename):
            return CubesuiteOpener()
