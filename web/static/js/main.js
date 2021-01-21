/*!
    * Start Bootstrap - SB Admin v6.0.2 (https://startbootstrap.com/template/sb-admin)
    * Copyright 2013-2020 Start Bootstrap
    * Licensed under MIT (https://github.com/StartBootstrap/startbootstrap-sb-admin/blob/master/LICENSE)
    */
import {Wireguard} from "./modules/wireguard.mjs";
import {WireguardIface} from "./modules/wireguard-iface.mjs";
import {WireguardPeer} from "./modules/wireguard-peer.mjs";

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

    Wireguard.load();
    WireguardIface.load();
    WireguardPeer.load();

})(jQuery);