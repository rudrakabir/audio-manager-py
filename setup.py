from setuptools import setup, find_packages

setup(
    name="audio_manager",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'PyQt6>=6.4.0',
        'soundfile>=0.10.3',
        'sounddevice>=0.4.3',
        'numpy>=1.21.0',
        'openai-whisper>=20231117'
    ],
    entry_points={
        'console_scripts': [
            'audio-manager=run:main',
        ],
    }
)