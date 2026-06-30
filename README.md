# ColdFront Plugin Demo

A simple demo plugin for ColdFront that will show compute usage from an external source.
The demo is set up to read a Pandas dataframe containing usage for testing. In a production
environment it may be more desirable to pull metrics from an external source of truth,
such as XDMoD or a Prometheus server.

## Installation

Clone the GitHub repository, e.g.

```git clone git@github.com:SouthernMethodistUniversity/cf_plugin_demo.git```

From your ColdFront repository,

```uv add <path to>/cf_plugin_demo```

Note: it may be necessary to edit the minimum Python version in ColdFront's
`pyproject.toml` to be `requires-python = ">=3.12"`.

### Modify settings

Add `cf_plugin_demo` to the `INSTALLED_APPS` of Coldfront --- in `coldfront/config/base.py`
add

```
# Add CF Plugin Demo
INSTALLED_APPS += [
    "cf_plugin_demo"
]
```

In `coldfront/config/core.py` add:

```
# -----------------------------------------------------------------------------
# Demo Plugin Functionality
# -----------------------------------------------------------------------------
CF_PLUGIN_DEMO_ENABLED = ENV.bool("CF_PLUGIN_DEMO_ENABLED", default=True)
SETTINGS_EXPORT += ["CF_PLUGIN_DEMO_ENABLED"]
```

In `coldfront/config/settings.py` add settings for the plugin, e.g.

```
CF_PLUGIN_DEMO_COMPUTE_ACCOUNT_ATTRIBUTE_NAME = ENV.str('CF_PLUGIN_DEMO_COMPUTE_ACCOUNT_ATTRIBUTE_NAME',
                                                          default='slurm_account_name')
# get the file path for the DF from settings
CF_PLUGIN_DEMO_AGGREGATE_ACCOUNT_DF_PATH = ENV.str('CF_PLUGIN_DEMO_AGGREGATE_ACCOUNT_DF_PATH', default='')
```

Add the URLs to `coldfront/config/urls.py`:

```
if "cf_plugin_demo" in settings.INSTALLED_APPS:
    _patterns.append(path("reports/", include("cf_plugin_demo.urls")))
```

Finally, add links to the navigation bar (at this point the page is available at
`COLDFRONT_URL/reports/stat-cards` but is not linked.) In `coldfront/templates/common/authorized_navbar.html` add

```
        {% if settings.CF_PLUGIN_DEMO_ENABLED %}
          {% include 'cf_plugin_demo/navbar.html' %}
        {% endif %}
```