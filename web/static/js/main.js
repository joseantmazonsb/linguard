/*!
    * Start Bootstrap - SB Admin v6.0.2 (https://startbootstrap.com/template/sb-admin)
    * Copyright 2013-2020 Start Bootstrap
    * Licensed under MIT (https://github.com/StartBootstrap/startbootstrap-sb-admin/blob/master/LICENSE)
    */
import {postJSON} from "./modules/utils.mjs";

"use strict";

(function($) {

    // Add active state to sidbar nav links
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

    const startOrStopIfaceBtn = $(".startOrStopIfaceBtn");
    startOrStopIfaceBtn.click(function(e) {
        const button = e.target;
        const iface = button.value;
        const action = button.innerText;

        const url = "/wireguard/interfaces/" + iface;
        const data = JSON.stringify({"action": action})
        const alertContainer = "wgIfacesHeader";
        const alertType = "danger";
        const loadFeedback = "wgIface-"+iface+"-loading"

        postJSON(url, alertContainer, alertType, loadFeedback, data);
    });

    const restartIfaceBtn = $(".restartIfaceBtn");
    restartIfaceBtn.click(function(e) {
        const iface = e.target.value;
        const action = "restart";

        const url = "/wireguard/interfaces/" + iface;
        const data = JSON.stringify({"action": action})
        const alertContainer = "wgIfacesHeader";
        const alertType = "danger";
        const loadFeedback = "wgIface-"+iface+"-loading"

        postJSON(url, alertContainer, alertType, loadFeedback, data);
    });

    const ifaceNameInput = $("#ifaceName");
    ifaceNameInput.click(function (e) {
        if (ifaceNameInput.attr("clicked") === "yes") return;
        ifaceNameInput.attr("clicked", "yes");
        const noBorder = "border-0";
        if (ifaceNameInput.hasClass(noBorder)) {
            ifaceNameInput.attr("readonly", false);
            ifaceNameInput.removeClass(noBorder);
        }
        else {
            ifaceNameInput.addClass(noBorder);
            ifaceNameInput.attr("readonly", true);
        }
    });
    ifaceNameInput.focusout(function (e) {
        ifaceNameInput.attr("clicked", "no");
        const noBorder = "border-0"
        ifaceNameInput.addClass(noBorder);
        ifaceNameInput.attr("readonly", true);
    });

})(jQuery);