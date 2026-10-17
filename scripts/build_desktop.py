"""Build on the destination OS. Each invocation has isolated build/output folders."""

from datetime import datetime
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import os
import plistlib
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from branding import APP_NAME, VERSION, BUNDLE_ID, ICON_PNG, ICON_ICO, ICON_ICNS


def prepare_macos_renderer(root, workspace):
    """Brand the native renderer too, so the macOS Dock doesn't say Flet."""
    from flet_desktop import get_package_bin_dir
    from flet.utils import safe_tar_extractall
    extracted = workspace / 'renderer'
    extracted.mkdir()
    with tarfile.open(Path(get_package_bin_dir()) / 'flet-macos.tar.gz', 'r:gz') as archive:
        safe_tar_extractall(archive, str(extracted))
    app = extracted / 'Flet.app'
    renamed = extracted / f'{APP_NAME}.app'
    app.rename(renamed)
    info = renamed / 'Contents' / 'Info.plist'
    with info.open('rb') as source:
        metadata = plistlib.load(source)
    metadata.update(CFBundleName=APP_NAME, CFBundleDisplayName=APP_NAME,
        CFBundleIdentifier=BUNDLE_ID + '.renderer', CFBundleShortVersionString=VERSION,
        CFBundleIconFile='FocusNest.icns')
    metadata.pop('CFBundleIconName', None)
    with info.open('wb') as destination:
        plistlib.dump(metadata, destination)
    shutil.copy2(root / 'src' / 'assets' / ICON_ICNS, renamed / 'Contents' / 'Resources' / 'FocusNest.icns')
    subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(renamed)], check=True)
    packaged = workspace / 'runtime-package'
    packaged.mkdir()
    with tarfile.open(packaged / 'flet-macos.tar.gz', 'w:gz') as archive:
        archive.add(renamed, arcname=f'{APP_NAME}.app')
    return packaged


def main():
    root = ROOT
    target = f'{sys.platform}-{platform.machine()}'
    output = root / 'dist' / f'{target}-{datetime.now():%Y%m%d-%H%M%S-%f}'
    output.mkdir(parents=True)
    workspace = Path(tempfile.mkdtemp(prefix='focusnest-build-'))
    icon = ICON_ICO if sys.platform == 'win32' else ICON_PNG
    args = [sys.executable, '-m', 'flet_cli.cli', 'pack', str(root / 'src' / 'main.py'),
        '--name', APP_NAME, '--product-name', APP_NAME, '--product-version', VERSION,
        '--icon', str(root / 'src' / 'assets' / icon),
        '--distpath', str(output), '--add-data', f"{root / 'src' / 'assets'}{';' if sys.platform == 'win32' else ':'}assets",
        '--hidden-import', 'flet_desktop', '--yes']
    environment = dict(os.environ)
    if sys.platform == 'darwin':
        runtime = prepare_macos_renderer(root, workspace)
        environment['FOCUSNEST_RUNTIME_DIR'] = str(runtime)
        args = [sys.executable, '-m', 'PyInstaller', str(root / 'src' / 'main.py'),
            '--noconfirm', '--noconsole', '--onefile', '--name', APP_NAME,
            '--icon', str(root / 'src' / 'assets' / ICON_ICNS),
            '--distpath', str(output), '--osx-bundle-identifier', BUNDLE_ID,
            '--additional-hooks-dir', str(root / 'packaging' / 'hooks'),
            '--hidden-import', 'flet_desktop', '--add-data', f"{root / 'src' / 'assets'}:assets"]
    else:
        args += ['--onedir']
    if sys.platform == 'win32':
        args += ['--hidden-import', 'plyer.platforms.win.libs.balloontip', '--file-version', VERSION + '.0']
    print(f'Building in {workspace}; output: {output}', flush=True)
    subprocess.run(args, cwd=workspace, env=environment, check=True)
    expected = output / (f'{APP_NAME}.app' if sys.platform == 'darwin' else APP_NAME)
    if not expected.exists():
        raise RuntimeError(f'Build did not produce {expected}. Inspect the build logs in {workspace}.')
    if sys.platform == 'darwin':
        info = expected / 'Contents' / 'Info.plist'
        with info.open('rb') as source:
            metadata = plistlib.load(source)
        metadata.update(CFBundleName=APP_NAME, CFBundleDisplayName=APP_NAME,
            CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION)
        with info.open('wb') as destination:
            plistlib.dump(metadata, destination)
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(expected)], check=True)
    # Keep the build directory for diagnostics; never clean a user's build tree.
    archive = shutil.make_archive(str(output / f'{APP_NAME}-{VERSION}-{target}'), 'zip', root_dir=output, base_dir=expected.name)
    if sys.platform == 'darwin':
        image_root = workspace / 'disk-image'
        image_root.mkdir()
        shutil.copytree(expected, image_root / expected.name, symlinks=True)
        (image_root / 'Applications').symlink_to('/Applications')
        subprocess.run(['hdiutil', 'create', '-volname', APP_NAME, '-srcfolder', str(image_root),
            '-format', 'UDZO', str(output / f'{APP_NAME}-{VERSION}-{target}.dmg')], check=True)
    elif sys.platform.startswith('linux'):
        stage = workspace / 'deb-root'
        package_root = stage / 'opt' / 'focusnest'
        shutil.copytree(expected, package_root)
        (stage / 'usr' / 'bin').mkdir(parents=True)
        (stage / 'usr' / 'bin' / APP_NAME).symlink_to('/opt/focusnest/' + APP_NAME)
        desktop = stage / 'usr' / 'share' / 'applications'
        desktop.mkdir(parents=True)
        shutil.copy2(root / 'packaging' / 'focusnest.desktop', desktop)
        icons = stage / 'usr' / 'share' / 'icons' / 'hicolor' / '256x256' / 'apps'
        icons.mkdir(parents=True)
        shutil.copy2(root / 'src' / 'assets' / 'focusnest-256.png', icons / 'focusnest.png')
        control = stage / 'DEBIAN'
        control.mkdir()
        architecture = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(platform.machine())
        if not architecture:
            raise RuntimeError('Unsupported Debian architecture: ' + platform.machine())
        (control / 'control').write_text(
            f'Package: focusnest\nVersion: {VERSION}\nSection: education\nPriority: optional\n'
            f'Architecture: {architecture}\nMaintainer: FocusNest maintainers\n'
            'Depends: libgtk-3-0, libasound2, libmpv1 | libmpv2\nRecommends: libnotify-bin\n'
            'Description: Focus timer with recoverable sessions and local task tracking\n')
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage),
            str(output / f'{APP_NAME}-{VERSION}-{architecture}.deb')], check=True)
    print(f'Built: {expected}\nArchive: {archive}\nBuild logs/spec: {workspace}', flush=True)


if __name__ == '__main__':
    main()
