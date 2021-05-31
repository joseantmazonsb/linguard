export {
    postJSON, AlertType, prependAlert
}

(function($) {
    $("[data-toggle=popover]").popover();
    // Add active state to sidebar nav links
    const path = window.location.href; // because the 'href' property of the DOM element is the absolute path
        $("#layoutSidenav_nav .sb-sidenav a.nav-link").each(function() {
            if (this.href === path) {
                $(this).addClass("active");
            }
        });
    // Toggle the side navigation
    $("#sidebarToggle").on("click", function(e) {
        e.preventDefault();
        $("body").toggleClass("sb-sidenav-toggled");
    });
})(jQuery);

const AlertType = Object.freeze({
    "DANGER": "danger",
    "WARN": "warning",
    "SUCCESS": "success",
    "INFO": "info",
});

/**
 * Perform a POST request to a given url and display an alert if the server returns a non-successful HTTP code.
 * This request may include JSON data.
 * @param url URL where the request will be sent.
 * @param alertContainer Id of the HTML element where to place an alert if something goes wrong.
 * @param alertType Type of the boostrap alert to be shown if anything goes wrong (danger, warning, info...).
 * @param loadFeedback Id of the HTML element to be used as visual feedback (a loading circle or bar, for example).
 * @param jsonData [Optional] JSON data to post.
 */
function postJSON(url, alertContainer, alertType = AlertType.DANGER, loadFeedback, jsonData = null) {
    const loadItem = $("#"+loadFeedback);
    $.ajax({
        type: "post",
        url: url,
        data: jsonData,
        dataType: 'json',
        contentType: 'application/json',
        beforeSend : function () {
            loadItem.show();
        },
        success: function () {
            location.reload();
        },
        error: function(resp) {
            prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"],
                alertType);
        },
        complete: function () {
            loadItem.hide();
        },
    });
}

let previousAlert;

/**
 * Prepend a bootstrap alert to a given HTML object.
 * @param prependTo Id of the HTML object to prepend the alert.
 * @param text Text of the alert.
 * @param alertType Type of the alert: danger, warning, info...
 * @param delay Amount of time (millis) before automatically closing the alert. Use 0 to avoid auto close.
 * @param unique
 * @param onEnd
 */
function prependAlert(prependTo, text, alertType = AlertType.DANGER, delay=7000, unique = false, onEnd) {
    const salt = getRndInteger();
    const alertId = "alert-"+salt;
    const closeId = "close-"+salt;

    let iconClass = "fas fa-exclamation-circle";
    switch (alertType) {
        case AlertType.WARN:
            iconClass = "fas fa-exclamation-triangle"
            break;
        case AlertType.SUCCESS:
            iconClass = "fas fa-check-circle"
            break;
        case AlertType.INFO:
            iconClass = "fas fa-info-circle"
            break;
        default:
            break;
    }
    let icon = '<i class="'+iconClass+' mr-2"></i>'

    const alert = "<div id=\""+alertId+"\" class=\"alert alert-"+alertType + " alert-dismissible fade show\" " +
        "role=\"alert\">" + icon + text +"\n" +
        "     <button type=\"button\" class=\"close\" id='"+closeId+"' aria-label=\"Close\">\n" +
        "         <span aria-hidden=\"true\">&times;</span>\n" +
        "    </button>\n" +
        "</div>"
    const container = $("#"+prependTo);
    if (unique && previousAlert !== undefined && previousAlert.type !== AlertType.DANGER) {
        fadeHTMLElement(previousAlert.id, 0, 200, 500, onEnd);
    }

    previousAlert = {"id": alertId, "type": alertType};
    $(alert).prependTo(container).hide().slideDown();
    $("#"+closeId).click(function (e) {
        fadeHTMLElement(alertId, 0, 200, 500, onEnd);
    });
    if (delay > 0) {
        fadeHTMLElement(alertId, delay, 500, 500, onEnd);
    }
}

/**
 * Generate a random integer between min and max (both included).
 * @param min
 * @param max
 * @returns {number}
 */
function getRndInteger(min=0, max=9999999) {
    return Math.floor(Math.random() * (max - min + 1) ) + min;
}

/**
 * Fade out an html element and remove it.
 * @param id Id of the element.
 * @param delay Time (millis) before fade out.
 * @param fadeDuration Duration (millis) of the fade effect.
 * @param slideDuration Duration (millis) of the slide effect.
 * @param onEnd Function to be called once the alert is gone and removed.
 */
function fadeHTMLElement(id, delay, fadeDuration = 500, slideDuration = 500, onEnd = null) {
    setTimeout(function() {
        $("#"+id).fadeTo(fadeDuration, 0).slideUp(slideDuration, function(){
            $(this).remove();
            if (typeof(onEnd) === "function") {
                onEnd();
            }
        });
    }, delay);
}