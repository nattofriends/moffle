/**
 * Highlight key lines.
 */
function Highlight() {
    this.lines = $(".js-line-no-highlight");
    this.highlightClass = 'irc-highlight';

    if (window.location.pathname !== "/search/") {

        /* Maybe highlight anchor text on load (only lines, not #end) */
        var hash = $(location).attr('hash');

        if (hash.charAt(1) == "L") {
            $(hash).parent().addClass(this.highlightClass);
        }

        this.lines.click($.proxy(this.onClick, this));
    }
}

Highlight.prototype.onClick = function(evt) {
    this.lines.parent().removeClass(this.highlightClass);
    $(evt.target).parent().addClass(this.highlightClass);
};


/**
 * Autofilter binds to a input with attribute data-filter-target
 * and targets children with data-filter-value of whatever
 * is matched by the selector value of data-filter-target.
 */
function Autofilter() {
    var form = $(".prefix-search-form");
    this.bind = $("[data-filter-target]");
    this.targets = $(this.bind.attr("data-filter-target")).children("[data-filter-value]");

    this.bind.bind('input', $.proxy(this.bindChange, this));
    form.submit($.proxy(this.doNothing, this));
}

Autofilter.prototype.doNothing = function(evt) {
    evt.preventDefault();
    evt.stopPropagation();
};

/**
 * Matches are case-insensitive.
 *
 * As as concession to the intended usage of this
 * component, we'll allow matches from the second
 * character if the first is '#'...
 */
Autofilter.prototype.bindChange = function(evt) {
    var search = this.bind.val().toLowerCase();

    this.targets.each(function(index) {
        var thisObj = $(this);
        var targetValue = thisObj.attr("data-filter-value").toLowerCase();

        if ((targetValue.indexOf(search) == 0) ||
            (targetValue.indexOf(search) == 1 && targetValue.charAt(0) == "#")
        ) {
            thisObj.show();
        } else {
            thisObj.hide();
        }
    });
}

function AjaxSearch(network, channels, query, maxSegment) {
    this.network = network;
    this.channels = channels;
    this.query = query;
    this.maxSegment = maxSegment;

    this.segment = 0;

    this.container = $(".js-results-container");
    this.message = $(".js-loading-spinner");
    this.noResults = $(".no-results");

    this.setupAjax();
}

AjaxSearch.prototype.onSuccess = function(html) {
    this.container.append(html);

    /* Kind of inefficient, eh? */
    new MovementTooltip();

    this.segment += 1;

    if (this.segment <= this.maxSegment) {
        this.setupAjax();
    } else {
        this.message.hide();
 
        if (this.container.children().length == 0) {
            this.noResults.removeClass("hidden");
        }
    }
};

AjaxSearch.prototype.setupAjax = function() {
    $.ajax({
        url: "/search/chunk",
        data: {
            network: this.network,
            channel: this.channels,
            text: this.query,
            segment: this.segment
        }
    }).done($.proxy(this.onSuccess, this));
};

/**
 * Hide the entire breadcrumb container when there are
 * no breadcrumbs (i.e. the front page) on mobile
 */
function MobileBreadcrumb() {
    // Yes, I know this is a bad thing to put in a hardcoded string
    if (window.matchMedia("(max-width: 767px)").matches && $(".breadcrumb").children().length == 0) {
        $(".breadcrumb").hide();
    }
}

function MovementTooltip() {
    $('[data-toggle="tooltip"]').tooltip();
}

function PrivateMessages() {
    this.pm = $(".js-pm-hide").not("[data-filter-value^='#']");
    this.pmShow = $(".js-pm-action-show");
    this.pmHide = $(".js-pm-action-hide");

    if (this.pm.length > 0) {
        this.pm.addClass("hidden");
        this.pmShow.removeClass("hidden");
        this.pmShow.click($.proxy(this.onClick, this));
        this.pmHide.click($.proxy(this.onClick, this));
        this.hidden = true;
    }

}

PrivateMessages.prototype.onClick = function (evt) {
    if (this.hidden === true) {
        this.hidden = false;
        this.pm.removeClass("hidden");
        this.pmShow.addClass("hidden");
        this.pmHide.removeClass("hidden");
    } else {
        this.hidden = true;
        this.pm.addClass("hidden");
        this.pmShow.removeClass("hidden");
        this.pmHide.addClass("hidden");
    }

    evt.preventDefault();
    evt.stopPropagation();
};

function LocaleOverride() {
    $(window).keypress(function (evt) {
        if (evt.which == 108) { // 'l'
            var pref = window.prompt("Enter your preferred language (ISO-639-1, thanks)");

            if (pref !== null) {
                document.cookie = "lang=" + pref;
                location.reload();
            }
        }
    });
}
