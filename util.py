CONTEXT_PROCESSORS = []

TEMPLATE_FILTERS = []

def delay_context_processor(f):
    CONTEXT_PROCESSORS.append(f)
    return f

def register_context_processors(app):
    for cp in CONTEXT_PROCESSORS:
        app.context_processor(cp)

def delay_template_filter(filter_name):
    def inner(f):
        TEMPLATE_FILTERS.append((filter_name, f))
        return f
    return inner

def register_template_filters(app):
    for filter_name, tf in TEMPLATE_FILTERS:
        app.template_filter(filter_name)(tf)

class Scope:
    NETWORK = "network"
    CHANNEL = "channel"
    DATE = "date"
