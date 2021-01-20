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

    function getRndInteger(min=0, max=9999999) {
      return Math.floor(Math.random() * (max - min + 1) ) + min;
    }

    function prependWireguardAlert(text) {
        prependAlert("wgIfacesHeader", text, "danger");
    }

    function prependAlert(prependTo, text, alertType = "warning", delay=7000) {
        const id = "alert-"+getRndInteger();
        const alert = "<div id=\""+id+"\" class=\"alert alert-"+alertType + " alert-dismissible fade show\" role=\"alert\">\n" +
            text +
            "     <button type=\"button\" class=\"close\" data-dismiss=\"alert\" aria-label=\"Close\">\n" +
            "         <span aria-hidden=\"true\">&times;</span>\n" +
            "    </button>\n" +
            "</div>"
        $("#"+prependTo).prepend(alert);
        $("#"+id).delay(delay).fadeTo(500, 0).slideUp(500, function(){
            $(this).remove();
        });
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
            complete: function () {
                loadIcon.hide();
            },
            success: function () {
                location.reload();
            },
            error: function() {
                prependWireguardAlert("Unable to perform operation. Try again later.");
            }
        });
    }

    const restartIfaceBtn = $(".restartIfaceBtn");
    restartIfaceBtn.click(function(e) {
        const iface = e.target.value;
        const action = "restart"
        triggerInterfaceAction(action, iface);
    });

})(jQuery);