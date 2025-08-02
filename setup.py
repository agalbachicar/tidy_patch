"""Setup configuration file for the package."""

from setuptools import setup, find_packages

setup(
    name='llm-pr-reviewer',
    version='0.1.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    package_data={
        'llm_reviewer': ['config/*.json', 'config/*.yaml'],
    },
    include_package_data=True,
    install_requires=[
        'dataclasses',
        'ollama',
    ],
    entry_points={
        'console_scripts': [
            'llm-pr-reviewer=llm_reviewer.cli:main',
        ],
    },
    author='Agustin Alba Chicar',
    author_email='ag.albachicar@gmail.com',
    description='PoC for code review automation using LLMs.',
    long_description='',
    long_description_content_type='text/markdown',
    url='https://github.com/agalbachicar/tidy_patch',
    icense='Apache License 2.0',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Code Generators',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Development Status :: 3 - Alpha',
    ],
    python_requires='>=3.10',
)
