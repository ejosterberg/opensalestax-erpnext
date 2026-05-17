# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
"""Setup script for the opensalestax_erpnext Frappe app.

Installed via `bench get-app https://github.com/ejosterberg/opensalestax-erpnext`
followed by `bench install-app opensalestax_erpnext`. Bench reads
requirements.txt during get-app and pip-installs declared dependencies.
"""

from setuptools import find_packages, setup

with open("requirements.txt") as f:
	install_requires = [
		line.strip() for line in f.read().splitlines() if line.strip() and not line.startswith("#")
	]

from opensalestax_erpnext import __version__ as version

setup(
	name="opensalestax_erpnext",
	version=version,
	description="Destination-based US sales tax for ERPNext via the OpenSalesTax engine",
	author="Eric Osterberg",
	author_email="ejosterberg@gmail.com",
	url="https://github.com/ejosterberg/opensalestax-erpnext",
	license="Apache-2.0 OR GPL-2.0-or-later",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
	classifiers=[
		"License :: OSI Approved :: Apache Software License",
		"License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
		"Programming Language :: Python :: 3",
		"Programming Language :: Python :: 3.10",
		"Programming Language :: Python :: 3.14",
		"Framework :: Frappe",
	],
)
