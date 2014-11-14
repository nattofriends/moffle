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
};

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
};

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
