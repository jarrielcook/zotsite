import logging
from pathlib import Path
import json
import shutil
from zensols.actioncli import persisted
from zensols.zotsite import (
    AppConfig,
    DatabaseReader,
    NavCreateVisitor,
    RegexItemMapper,
    IdItemMapper,
    FileSystemCopyVisitor,
    PruneVisitor,
    Library,
    PrintVisitor,
    Walker,
)

logger = logging.getLogger(__name__)


class SiteCreator(object):
    """Create the Zotero content web site.

    """
    def __init__(self, config: AppConfig = None):
        cnf = config.populate()
        self.db = DatabaseReader(config.get_option_path('data_dir'),
                                 library_id=cnf.library_id)
        self.out_dir = config.get_option_path('out_dir', expect=False)
        self.config = config

    @property
    def walker(self) -> Walker:
        return Walker()

    @property
    @persisted('_library')
    def library(self) -> Library:
        lib = self.db.get_library()
        name_pat = self.config.get_option('name_pat', expect=False)
        if name_pat is not None:
            logger.info(f'filtering on \'{name_pat}\'')
            match_children = self.config.get_option_boolean(
                'match_children', expect=False)
            visitor = PruneVisitor(name_pat, match_children)
            self.walker.walk(lib, visitor)
        return lib

    @property
    @persisted('_itemmapper')
    def itemmapper(self):
        if 0:
            return RegexItemMapper(self.library, '.*\.pdf$', '[ ]')
        else:
            return IdItemMapper(self.library)

    def print_structure(self):
        """Print (sub)collections and papers in those collections as a tree.

        """
        self.walker.walk(self.library, PrintVisitor())

    def _write_meta(self, fname):
        """Write version and other metadata to the website, which is used during
        rending of the site.

        """
        if hasattr(self.config, 'pkg'):
            pkg = self.config.pkg
            meta = {'version': pkg.version,
                    'project_name': pkg.project_name}
        else:
            meta = {'version': '<none>',
                    'project_name': '<none>'}
        js = 'var zoteroMeta = {};'.format(json.dumps(meta))
        with open(fname, 'w') as f:
            f.write(js)

    def _create_tree_data(self):
        """Create the table of contents/tree info used by the navigation widget.

        """
        itemmapper = self.itemmapper
        js_dir = self.out_dir / 'js'
        nav_file = js_dir / 'zotero-tree-data.js'
        logger.info('creating js nav tree: {}'.format(nav_file))
        visitor = NavCreateVisitor(self.library, itemmapper)
        self.walker.walk(self.library, visitor)
        with open(nav_file, 'w') as f:
            f.write("var tree =\n")
            f.write(json.dumps(visitor.primary_roots, indent=2))
        meta_file = Path(js_dir, 'zotero-meta.js')
        logger.info('creating js metadata: {}'.format(meta_file))
        self._write_meta(meta_file)

    def _copy_storage(self):
        """Copy the storage contents, which is the location of the PDF (and other)
        documents that will be rendered in the site GUI.

        """
        dst = self.out_dir
        fsvisitor = FileSystemCopyVisitor(self.library, dst, self.itemmapper)
        logger.info(f'copying storage to {dst}')
        self.walker.walk(self.library, fsvisitor)

    def _copy_static_res(self, src: Path, dst: Path):
        """Copy static resources from the distribution package.

        :param src: the source package directory
        :param dst: the destination on the file system

        """
        logger.debug(f'copy: {src} -> {dst}'.format(src, dst))
        dst.mkdir(parents=True, exist_ok=True)
        for res in src.iterdir():
            res = res.name
            src_file = src / res
            dst_file = dst / res
            if src_file.is_dir():
                self._copy_static_res(src_file, dst_file)
            else:
                logger.debug(f'copy: {src_file} -> {dst_file}')
                shutil.copyfile(src_file, dst_file)

    def _copy_static(self):
        logger.info('copying static data -> {self.out_dir}')
        for src in 'src lib'.split():
            src_dir = self.config.resource_filename(f'resources/{src}')
            self._copy_static_res(src_dir, self.out_dir)

    def export(self):
        """Entry point method to export (create) the website.

        """
        #self.itemmapper = self._create_itemmapper()
        self._copy_static()
        self._create_tree_data()
        self._copy_storage()

    def tmp(self):
        self.print_structure()
