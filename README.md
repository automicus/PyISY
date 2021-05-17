## PyISY

### Python Library for the ISY Controller

This library allows for easy interaction with ISY nodes, programs, variables, and the network module. This class also allows for functions to be
assigned as handlers when ISY parameters are changed. ISY parameters can be
monitored automatically as changes are reported from the device.

**NOTE:** Significant changes have been made in V2, please refer to the [CHANGELOG](CHANGELOG.md) for details. It is recommended you do not update to the latest version without testing for any unknown breaking changes or impacts to your dependent code.

### Examples

See the [examples](examples/) folder for connection examples.

The full documentation is available at https://pyisy.readthedocs.io.

### Development Team

- Greg Laabs ([@overloadut]) - Maintainer
- Ryan Kraus ([@rmkraus]) - Creator
- Tim ([@shbatm]) - Version 2 Contributor

### Contributing

A note on contributing: contributions of any sort are more than welcome! This repo uses precommit hooks to validate all code. We use `black` to format our code, `isort` to sort our imports, `flake8` for linting and syntax checks, and `codespell` for spell check.

To use [pre-commit](https://pre-commit.com/#installation), see the installation instructions for more details.

Short version:

```shell
# From your copy of the pyisy repo folder:
pip install pre-commit
pre-commit install
```

A [VSCode DevContainer](https://code.visualstudio.com/docs/remote/containers#_getting-started) is also available to provide a consistent development environment.

Assuming you have the pre-requisites installed from the link above (VSCode, Docker, & Remote-Containers Extension), to get started:

1. Fork the repository.
2. Clone the repository to your computer.
3. Open the repository using Visual Studio code.
4. When you open this repository with Visual Studio code you are asked to "Reopen in Container", this will start the build of the container.
   - If you don't see this notification, open the command palette and select Remote-Containers: Reopen Folder in Container.
5. Once started, you will also have a `test_scripts/` folder with a copy of the example scripts to run in the container which won't be committed to the repo, so you can update them with your connection details and test directly on your ISY.

[@overloadut]: https://github.com/overloadut
[@rmkraus]: https://github.com/rmkraus
[@shbatm]: https://github.com/shbatm
