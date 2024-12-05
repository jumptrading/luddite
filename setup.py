from setuptools import setup

setup(
    name="luddite",
    version="1.0.4",
    author="Wim Glenn",
    author_email="hey@wimglenn.com",
    url="https://github.com/jumptrading/luddite",
    py_modules=["luddite"],
    description="Checks for out-of-date package versions",
    long_description=open("README.md").read(),
    classifiers=[
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
    ],
    entry_points={"console_scripts": ["luddite=luddite:main"]},
    install_requires=[
        "packaging",
        'colorama; platform_system == "Windows"',
        'futures; python_version < "3.2"',
    ],
    extras_require={
        # https://hynek.me/articles/conditional-python-dependencies/
        "dev": [
            "pytest >= 3.6.3",
            "pytest-cov",
            "pytest-mock",
            "pytest-socket",
        ],
    },
    options={"bdist_wheel": {"universal": True}},
)
