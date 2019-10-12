import setuptools

with open("README.md", "r") as readme:
    long_description = readme.read()

setuptools.setup(
    name="ezntfs",
    version="0.1.1",
    author="Matt",
    author_email="undecidabot@gmail.com",
    description="An easy-to-use wrapper for ntfs-3g on macOS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/undecidabot/ezntfs",
    license="Zlib",
    py_modules=["ezntfs"],
    packages=setuptools.find_packages(),
    classifiers=[
        "Environment :: Console",
        "License :: OSI Approved :: zlib/libpng License",
        "Operating System :: MacOS :: MacOS X",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Filesystems",
    ],
    python_requires='>=3.6',
    entry_points = {
        'console_scripts': ['ezntfs=ezntfs:main'],
    },
)
