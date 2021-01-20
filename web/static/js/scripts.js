/*!
    * Start Bootstrap - {{ app_name }} v6.0.2 (https://startbootstrap.com/template/sb-admin)
    * Copyright 2013-2020 Start Bootstrap
    * Licensed under MIT (https://github.com/StartBootstrap/startbootstrap-sb-admin/blob/master/LICENSE)
    */
    (function($) {
    "use strict";

    // Add active state to sidbar nav links
    var path = window.location.href; // because the 'href' property of the DOM element is the absolute path
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

    function prependWireguardAlert(text) {
        prependAlert("wgIfacesHeader", text, "danger");
    }

    /**
     * Prepend a bootstrap alert to a given HTML object.
     * @param prependTo Id of the HTML object to prepend the alert.
     * @param text Text of the alert.
     * @param alertType Type of the alert: danger, warning, info...
     * @param delay Amount of time (millis) before automatically closing the alert. Use 0 to avoid auto close.
     */
    function prependAlert(prependTo, text, alertType = "warning", delay=7000) {
        const salt = getRndInteger();
        const alertId = "alert-"+salt;
        const closeId = "close-"+salt;
        const alert = "<div id=\""+alertId+"\" class=\"alert alert-"+alertType + " alert-dismissible fade show\" " +
            "role=\"alert\">" + text +"\n" +
            "     <button type=\"button\" class=\"close\" id='"+closeId+"' aria-label=\"Close\">\n" +
            "         <span aria-hidden=\"true\">&times;</span>\n" +
            "    </button>\n" +
            "</div>"
        const container = $("#"+prependTo);
        $(alert).prependTo(container).hide().slideDown();
        $("#"+closeId).click(function (e) {
            fadeHTMLElement(alertId, 0, 200);
        });
        if (delay > 0) {
            fadeHTMLElement(alertId, delay);
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
     */
    function fadeHTMLElement(id, delay, fadeDuration = 500, slideDuration = 500) {
        setTimeout(function() {
            $("#"+id).fadeTo(fadeDuration, 0).slideUp(slideDuration, function(){
                $(this).remove();
            });
        }, delay);
    }

    const startOrStopIfaceBtn = $(".startOrStopIfaceBtn");
    startOrStopIfaceBtn.click(function(e) {
        const button = e.target;
        const iface = button.value;
        const action = button.innerText;
        triggerInterfaceAction(action, iface);
    });

    function triggerInterfaceAction(action, iface) {
        const url = "/wireguard/interfaces/" + iface;
        const loadIcon = $("#wgIface-"+iface+"-loading");
        $.ajax({
            type: "post",
            url: url,
            data: JSON.stringify({"action": action}),
            dataType: 'json',
            contentType: 'application/json',
            beforeSend : function () {
                loadIcon.show();
            },
            success: function () {
                location.reload();
            },
            error: function(resp) {
                prependWireguardAlert("<strong>Oops, something went wrong</strong>: " + resp["responseText"]);
            },
            complete: function () {
                loadIcon.hide();
            },
        });
    }

    const restartIfaceBtn = $(".restartIfaceBtn");
    restartIfaceBtn.click(function(e) {
        const iface = e.target.value;
        const action = "restart"
        triggerInterfaceAction(action, iface);
    });

})(jQuery);