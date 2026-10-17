"""Export the approved, unmodified artwork into native application icon formats."""

from pathlib import Path

from PIL import Image


def main():
    root = Path(__file__).resolve().parents[1]
    master = root / 'design' / 'branding' / 'focusnest-mark-master.png'
    assets = root / 'src' / 'assets'
    with Image.open(master) as image:
        rgba = image.convert('RGBA')
        if rgba.getchannel('A').getextrema()[0] == 255:
            raise ValueError('The logo master must have a transparent background.')
        # Artwork extraction was done with image generation; these are format/size exports only.
        icon = rgba.resize((1024, 1024), Image.Resampling.LANCZOS)
        icon.save(assets / 'focusnest-icon.png')
        icon.save(assets / 'focusnest.ico', format='ICO', sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
        icon.save(assets / 'focusnest.icns', format='ICNS')
        icon.resize((256, 256), Image.Resampling.LANCZOS).save(assets / 'focusnest-256.png')
    print('Exported FocusNest PNG, ICO, ICNS, and Linux 256px icon into src/assets/.')


if __name__ == '__main__':
    main()
