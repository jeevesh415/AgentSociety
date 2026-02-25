Contributing to AgentSociety 2
===============================

Thank you for your interest in contributing to AgentSociety 2!

Ways to Contribute
------------------

* **Report bugs**: Open an issue with a reproducible example
* **Suggest features**: Share your ideas for improvements
* **Submit code**: Open a pull request with your changes
* **Improve docs**: Help make the documentation clearer
* **Share examples**: Add useful examples to the collection

Reporting Bugs
--------------

When reporting a bug, please include:

* Python version
* AgentSociety 2 version
* Minimal reproducible example
* Expected vs actual behavior
* Any error messages or traceback

See the bug report template for details.

Suggesting Features
-------------------

Feature suggestions are welcome! Please:

* Describe the use case clearly
* Explain why it would be useful
* Consider if it fits the project's scope
* Be open to discussion

Submitting Pull Requests
-------------------------

Before submitting a PR:

1. Check existing issues for related discussions
2. Fork the repository
3. Create a branch for your work
4. Make your changes with clear commit messages
5. Update documentation if needed
6. Submit your pull request

PR Guidelines
~~~~~~~~~~~~~

* Keep changes focused and atomic
* Follow the existing code style
* Add docstrings to new functions/classes
* Update relevant documentation
* Ensure CI passes

Code Review Process
~~~~~~~~~~~~~~~~~~~

All PRs go through code review:

* Maintainers will review your changes
* Address any feedback or requests
* Once approved, the PR will be merged
* Large changes may need multiple iterations

Development Setup
------------------

.. code-block:: bash

   # Clone your fork
   git clone https://github.com/your-username/agentsociety.git
   cd agentsociety

   # Install in development mode
   uv sync
   pip install -e "packages/agentsociety2[dev]"

   # Install pre-commit hooks
   cd packages/agentsociety2
   pre-commit install

Adding New Features
-------------------

When adding new features:

1. Open an issue to discuss first
2. Implement the feature
3. Update documentation
4. Add examples if helpful

Example Structure
~~~~~~~~~~~~~~~~~

.. code-block:: text

   tests/
   ├── test_agent.py
   ├── test_env.py
   └── test_storage.py

   agentsociety2/
   ├── new_module/
   │   ├── __init__.py
   │   ├── core.py
   │   └── utils.py
   └── new_module/
       ├── __init__.py
       └── implementation.py

Documentation Standards
------------------------

Docstrings should follow the Google style:

.. code-block:: python

   def example_function(param1: str, param2: int) -> bool:
       """Brief description of the function.

       Longer description with more details.

       Args:
           param1: Description of param1
           param2: Description of param2

       Returns:
           Description of return value

       Raises:
           ValueError: If something goes wrong
       """
       pass

Community Guidelines
--------------------

* Be respectful and constructive
* Welcome new contributors
* Focus on what is best for the community
* Show empathy towards other community members

Getting Help
------------

* **GitHub Issues**: For bugs and feature requests
* **GitHub Discussions**: For questions and ideas
* **Documentation**: Check the docs first

License
-------

By contributing to AgentSociety 2, you agree that your contributions
will be licensed under the Apache License 2.0.
