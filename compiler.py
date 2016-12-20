# -*- coding:utf-8 -*-
import os
from clang import *
from clang.cindex import *
import threading
import pickle
import sqlite3
import pprint
import platform


local_config = {
}

if platform.system() == 'Darwin':
    local_config['lib_path'] = '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/'
elif platform.system() == 'Windows':
    local_config['lib_path'] = 'D:\\'
elif platform.system() == 'Linux':
    local_config['lib_path'] = '/usr/lib/x86_64-unknown-linux'


EditingTranslationUnitOptions = (
        cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD |
        cindex.TranslationUnit.PARSE_PRECOMPILED_PREAMBLE |
        cindex.TranslationUnit.PARSE_CACHE_COMPLETION_RESULTS |
        cindex.TranslationUnit.PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION |
        0x200)

MacroExpendQTUOptions = (
    0x200
    )

def extend_normalize(sourceRange):
    return ((sourceRange.start.line, sourceRange.start.column),
            (sourceRange.end.line, sourceRange.end.column))

def path_normalize(file_path):
    file_path = os.path.normpath(file_path)
    file_path = os.path.normcase(file_path)
    return file_path


class Compiler:
    def __init__(self, filename):
        self.filename = filename
        if not cindex.Config.loaded:
            cindex.Config.set_library_path(local_config['lib_path'])
            cindex.Config.compatibility_check = False
        self.clang_index = cindex.Index.create()
        self.errors = None
        self.fileinfo = dict()
        self.args = None
        self.unsaved_files = None

    def get_include_files(self):
        for file_inclusions in self.clang.get_includes():
            yield (path_normalize(file_inclusions.include.name), (
                        file_inclusions.location.file.name,
                        file_inclusions.location.line))

    def parse(self, args, unsaved_files=None):
        self.args = args
        self.unsaved_files = unsaved_files
        self.clang = self.clang_index.parse(self.filename, args, unsaved_files, options=EditingTranslationUnitOptions)
        self.fileinfo['ModifyTime'] = os.stat(self.filename).st_mtime
        inc_list = list()
        for f in self.get_include_files():
            inc_list.append((f[0], os.stat(f[0]).st_mtime))
        self.fileinfo['HeaderModifyTime'] = inc_list
        self.get_errors()

    def reparse(self, unsaved_files=None):
        self.clang.reparse(unsaved_files)

    def has_file(self, filename):
        if os.path.samefile(filename, self.filename):
            return True
        for (f, pos) in self.get_include_files():
            if os.path.samefile(f, filename):
                return True
        return False

    def get_usr(self, filename, line, column):
        try:
            position = SourceLocation.from_position(
                self.clang,
                self.clang.get_file(filename),
                line,
                column)
            cursor = self.clang.cursor.from_location(self.clang, position)
            return cursor.get_usr()
        except:
            return None

    def get_defination(self, filename, line, column):
        try:
            position = SourceLocation.from_position(
                    self.clang,
                    self.clang.get_file(filename),
                    line,
                    column)
            cursor = self.clang.cursor.from_location(self.clang, position)
            ref = cursor.referenced or cursor.get_defination()   # 两者有什么区别？
            pos = ref.location
            return (pos.file, pos.line, pos.column)
        except:
            return None

    def get_macro_expend(self, filename, line, column):
        position = SourceLocation.from_position(
                    self.clang,
                    self.clang.get_file(filename),
                    line,
                    column)
        temp_cindex = cindex.Index.create()
        temp_compiler = temp_cindex.parse(self.filename, self.args, self.unsaved_files, options=0)
        # tokens = self.clang.get_tokens(position)
        for cur in temp_compiler.cursor.walk_preorder():
            print(cur.spelling)
        # for cur in self.clang.cursor.walk_preorder():

        #     if cur.kind == CursorKind.MACRO_INSTANTIATION:
        #         if os.path.samefile(cur.location.file.name, self.filename):
        #             ext = SourceRange.from_locations(
        #                     SourceLocation.from_offset(temp_compiler,
        #                                         File.from_name(temp_compiler, cur.location.file.name),
        #                                         cur.extent.start.offset
        #                         ),
        #                     SourceLocation.from_offset(temp_compiler,
        #                                         File.from_name(temp_compiler, cur.location.file.name),
        #                                         cur.extent.end.offset
        #                         )
        #                 )
        #             for c in temp_compiler.cursor.walk_preorder():
        #                 if c.extent in ext:
        #                     print(cur.spelling, '->', c.spelling)
        return ' '
        # cursor = self.clang.cursor.from_location(self.clang, position)
        # print(''.join(map(lambda m:m.spelling, cursor.walk_preorder())))

    # TODO: 修改返回结果类型，排除clang对象
    def code_complete(self, line, column, unsaved_content, filename=None):
        unsaved = [(self.filename, unsaved_content)]
        if filename is None:
            filename = self.filename
        return self.clang.codeComplete(
                                    filename,
                                    line=line, column=column,
                                    unsaved_files=unsaved,
                                    include_macros=True,
                                    include_code_patterns=True,
                                    include_brief_comments=True
                                    )

    def get_errors(self):
        if self.errors is not None:
            return self.errors
        severity_list = ['Ignored', 'Note', 'Warning', 'Error', 'Fatal']
        error_list = []
        for error in self.clang.diagnostics:
            if error.location.file is None:
                continue
            error_dict = dict()
            # print(error.spelling)
            error_dict['file'] = error.location.file.name
            error_dict['line'] = error.location.line
            error_dict['column'] = error.location.column
            error_dict['severity'] = severity_list[error.severity]
            error_dict['string'] = error.spelling
            fixit = list()
            for fix in error.fixits:
                pos = ((fix.range.start.line, fix.range.start.column),
                         (fix.range.end.line, fix.range.end.column))
                fixit.append((pos, fix.value))
            error_dict['fixit'] = fixit
            error_list.append(error_dict)
        self.errors = error_list
        return error_list

    def get_include(self, filename, line):
        for (f, pos) in self.get_include_files():
            if os.path.samefile(filename, pos[0]) and line == pos[1]:
                return f

    def dump_to_file(self, file_prefix):
        self.clang.save(file_prefix + '.clangdata')
        pickle.dump(
            (self.filename,
                self.fileinfo,
                self.errors), open(file_prefix + '.plugindata', 'wb'))

    def load_from_file(self, file_prefix):
        self.clang = self.clang_index.read(file_prefix + '.clangdata')
        self.filename, self.fileinfo, self.errors = pickle.load(open(file_prefix + '.plugindata', 'rb'))


class Projector:
    def __init__(self):
        self.work_path = ''
        self.files = dict()
        self.usr_include_path = list()
        self.sys_include_path = list()
        self.arguments = list()
        self.background_worker = None

    def get_compiler(self, filename):
        if self.background_worker and self.background_worker.isAlive():
            return None
        filename = path_normalize(filename)
        for (f, compiler) in self.files.items():
            if compiler.has_file(filename):
                return compiler
        return None

    def set_arguments(self, args):
        if self.background_worker and self.background_worker.isAlive():
            return None
        self.arguments = args

    def set_work_path(self, work_path):
        if self.background_worker and self.background_worker.isAlive():
            return None
        self.work_path = path_normalize(work_path)

    def add_sys_include_path(self, include_path):
        if self.background_worker and self.background_worker.isAlive():
            return None
        self.sys_include_path.append(path_normalize(include_path))

    def add_usr_include_path(self, include_path):
        if self.background_worker and self.background_worker.isAlive():
            return None
        self.usr_include_path.append(path_normalize(include_path))

    def add_file(self, filename):
        if self.background_worker and self.background_worker.isAlive():
            return None
        filename = path_normalize(filename)
        self.files[filename] = Compiler(filename)

    def need_parse(self, incs):
        for (f, t) in incs['HeaderModifyTime']:
            if t < os.stat(f).st_mtime:
                return True
        return False

    def compile(self, unsaved_files=None, progress_callback=None):
        if self.background_worker and self.background_worker.isAlive():
            return None
        def worker(self, unsaved_files, progress_callback):
            args = list(self.arguments)
            for sys_inc in self.sys_include_path:
                args.append('-isystem')
                args.append(sys_inc)

            for usr_inc in self.usr_include_path:
                args.append('-I')
                args.append(usr_inc)
            args.append('-Wall')
            args.append('-Wextra')
            # args.append('-Weverything')   # hardcore mode
            i = 1
            file_sum = len(self.files)
            def sub_worker(sub_args):
                nonlocal i
                nonlocal self
                filename, compiler = sub_args
                relpath = os.path.relpath(filename, self.work_path)
                astpath = os.path.join(self.work_path, '.clang_data')
                try:
                    os.makedirs(astpath)
                except:
                    pass
                astpath = os.path.join(astpath, relpath.replace('\\', '_'))
                try:
                    if os.stat(filename).st_mtime > os.stat(astpath + '.clangdata').st_mtime:
                        raise Exception("whatever...")
                    compiler.load_from_file(astpath)
                    if self.need_parse(compiler.fileinfo):
                        raise Exception("whatever...")
                except:
                    compiler.parse(args, unsaved_files)
                    compiler.get_errors()
                    compiler.dump_to_file(astpath)
                print(compiler.get_usr('D:\WorkSpace\Fujitsu_718\config.h', 26, 13))
                print(compiler.get_defination('D:\WorkSpace\Fujitsu_718\main.c', 688, 10))
                print(compiler.get_macro_expend('D:\WorkSpace\Fujitsu_718\main.c', 18, 10))
                i += 1
                if progress_callback:
                    progress_callback('Parsing [%d/%d] %s' % (i, file_sum, filename))

            for arg in self.files.items():
                sub_worker(arg)

            if progress_callback:
                progress_callback('All Done.')
        worker(self, unsaved_files, progress_callback)

    def re_compile(self, target_file, unsaved_files=None):
        if self.background_worker and self.background_worker.isAlive():
            return None
        def worker(self, target_file, unsaved_files):
            for (filename, compiler) in self.files.items():
                if compiler.has_file(target_file):
                    compiler.reparse(unsaved_files)
                    compiler.collect_symbols()
        self.background_worker = threading.Thread(target=worker, args=(self, target_file, unsaved_files))
        self.background_worker.start()

    def get_cursor_at(self, filename, line, column):
        if self.background_worker and self.background_worker.isAlive():
            return None
        f_compiler = self.get_compiler(filename)
        return f_compiler.get_cursor_at(line, column, filename) if f_compiler else None

    def get_def_of(self, filename, line, column):
        if self.background_worker and self.background_worker.isAlive():
            return None
        cur = self.get_cursor_at(filename, line, column)
        if cur is None:
            return None
        if cur.get_definition():
            return cur.get_definition()
        if cur.referenced is None:
            return None
        usr = cur.referenced.get_usr()
        for (f, compiler) in self.files.items():
            if usr in compiler.symbol_def_table:
                return compiler.symbol_def_table[usr]
        return None

    def get_def_body_of(self, filename, line, column):
        if self.background_worker and self.background_worker.isAlive():
            return None
        f_compiler = self.get_compiler(filename)
        cur = self.get_cursor_at(filename, line, column)
        if cur is None:
            return None
        if cur.get_definition():
            cur = cur.get_definition()
        elif cur.referenced is None:
            cur = cur.referenced
        return f_compiler.clang.get_extent(filename, [cur.extent.start, cur.extent.end])

    def find_cursor(self, filename, line, column):
        if self.background_worker and self.background_worker.isAlive():
            return None
        cursor = self.get_cursor_at(filename, line, column)
        def_cur = cursor.get_definition() or cursor.referenced
        if def_cur is None:
            return None
        usr = def_cur.get_usr()
        all_referenced = list()
        for (f, compiler) in self.files.items():
            cur_lst = compiler.find_symbols(usr)
            if cur_lst:
                all_referenced.extend(cur_lst)
        return all_referenced

    def get_errors(self, filename):
        if self.background_worker and self.background_worker.isAlive():
            return None
        f_compiler = self.get_compiler(filename)
        if f_compiler:
            return f_compiler.get_errors()
        else:
            return None

    def get_include(self, filename, line):
        if self.background_worker and self.background_worker.isAlive():
            return None
        f_compiler = self.get_compiler(filename)
        return f_compiler.get_include(filename, line)

    def get_line(self, filename, line):
        if self.background_worker and self.background_worker.isAlive():
            return None
        import codecs
        content = codecs.open(filename, 'r', 'utf-8', 'ignore').readlines()[line-1]
        return content.strip()

    def code_complete(self, filename, line, column, unsaved_content):
        if self.background_worker and self.background_worker.isAlive():
            return None
        f_compiler = self.get_compiler(filename)
        if f_compiler is None:
            return None
        return f_compiler.code_complete(line, column, unsaved_content, filename)


if __name__ == '__main__':
    
    proj = Projector()
    proj.set_work_path(r'D:\WorkSpace\Fujitsu_718')
    proj.add_usr_include_path(r'D:\WorkSpace\Fujitsu_718')
    proj.add_usr_include_path(r'D:\WorkSpace\Fujitsu_718\Fujitsu718')
    proj.add_file('D:\WorkSpace\Fujitsu_718\main.c')
    proj.add_file(r'D:\workspace\Fujitsu_718\math.c')
    
    args = list()
    args.append( "-D__io=")
    args.append( "-D__direct=")
    args.append( "-D__CPU_MB95F718L__")
    args.append( "-D__IO_FAR")
    args.append( '-D__far=')
    args.append( "-D__EI()={}")
    args.append( "-D__DI()={}")
    args.append( "-D__set_il(x)={}")
    args.append( "-D__wait_nop()={}")
    args.append( "-D__asm(x)={}")
    args.append( "-D__interrupt=")
    args.append( "-std=c99")
    proj.set_arguments(args)
    from time import clock, sleep
    start=clock()
    proj.compile()
    finish=clock()
    print((finish-start))

    # proj.re_compile(r'D:\clang\Fujitsu_718\main.c')


