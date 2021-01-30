import {AlertType, prependAlert} from "./utils.mjs";

export { WireguardIface }

class WireguardIface {

    static load() {
        const ifaceNameInput = $("#name");
        const gwIface = $("#gw");
        const onUp = $("#onUp")
        const onDown = $("#onDown")
        const loadFeeback = $("#wgLoading");
        const alertContainer = "wgIfaceConfig";

        let oldName = ifaceNameInput.val();
        let oldGw = gwIface.val();

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

        function replaceOnUpDownComands(oldVal, newVal) {
            let value = onUp.val()
            value = value.replaceAll(oldVal, newVal)
            onUp.val(value)

            value = onDown.val()
            value = value.replaceAll(oldVal, newVal)
            onDown.val(value)
        }

        ifaceNameInput.focusout(function (e) {
            ifaceNameInput.attr("clicked", "no");
            const noBorder = "border-0"
            ifaceNameInput.addClass(noBorder);
            ifaceNameInput.attr("readonly", true);

            const newName = ifaceNameInput.val();
            if (!newName) return;
            replaceOnUpDownComands(oldName, newName);
            oldName = newName;
        });

        gwIface.focusout(function (e) {
            const newGw = gwIface.val();
            if (!newGw) return;
            replaceOnUpDownComands(oldGw, newGw);
            oldGw = newGw;
        });

        const resetIfaceBtn = $("#resetBtn");
        resetIfaceBtn.click(function (e) {
           location.reload();
        });

        function sendPost(url, onSuccess, onSuccessAlertType = AlertType.SUCCESS, data=null) {
            $.ajax({
                type: "post",
                url: url,
                data: JSON.stringify({"data": data}),
                dataType: 'json',
                contentType: 'application/json',
                beforeSend : function () {
                    loadFeeback.show();
                },
                success: function (resp) {
                    prependAlert(alertContainer, onSuccess, onSuccessAlertType,
                        7000, true);
                },
                error: function(resp) {
                    prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"]);
                },
                complete: function (resp) {
                    loadFeeback.hide();
                },
            });
        }

        const saveIfaceBtn = $("#saveBtn");
        saveIfaceBtn.click(function (e) {
            const url = location.href+"/save";
            const data = {
                "name": $("#name").val(),
                "description": $("#description").val(),
                "gw_iface": $("#gw").val(),
                "ipv4_address": $("#ipv4").val(),
                "listen_port": $("#port").val(),
                "on_up": $("#onUp").val(),
                "on_down": $("#onDown").val(),
                "auto": autoStart
            };
            sendPost(url,"Changes saved! Don't forget to <strong>apply</strong> them before leaving.",
                AlertType.WARN, data)
        });

        const applytIfaceBtn = $("#applyBtn");
        applytIfaceBtn.click(function (e) {
            const url = location.href+"/apply";
            const data = {
                "name": $("#name").val(),
                "description": $("#description").val(),
                "gw_iface": $("#gw").val(),
                "ipv4_address": $("#ipv4").val(),
                "listen_port": $("#port").val(),
                "on_up": $("#onUp").val(),
                "on_down": $("#onDown").val(),
                "auto": autoStart
            };
            sendPost(url,"Configuration <strong>applied</strong>!", AlertType.SUCCESS, data)
        });

        const regenerateKeysBtn = $("#regenerateKeysBtn");
        regenerateKeysBtn.click(function (e) {
            const url = location.href+"/regenerate-keys";
            sendPost(url, "Keys regenerated!");
        });

        const addIfaceBtn = $("#addBtn");
        addIfaceBtn.click(function (e) {
            addIfaceBtn.attr("disabled", true);
            resetIfaceBtn.attr("disabled", true);
            const url = location.href.split("?")[0];
            updateCurrentIface();
            $.ajax({
                type: "post",
                url: url,
                data: JSON.stringify({"data": current_iface}), // Filled up in jinja template
                dataType: 'json',
                contentType: 'application/json',
                beforeSend : function () {
                    loadFeeback.show();
                },
                success: function (resp) {
                    prependAlert(alertContainer, "New interface added!", AlertType.SUCCESS, 1500, true, function () {
                        const baseUrl = location.protocol + "//" + location.hostname + ":" + location.port;
                        const url = baseUrl + "/wireguard";
                        location.replace(url);
                    });
                },
                error: function(resp) {
                    prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"]);
                    addIfaceBtn.attr("disabled", false);
                    resetIfaceBtn.attr("disabled", false);
                },
                complete: function (resp) {
                    loadFeeback.hide();
                },
            });
        });

        function updateCurrentIface() {
            current_iface.name = $("#name").val();
            current_iface.description = $("#description").val();
            current_iface.gw_iface = $("#gw").val();
            current_iface.ipv4_address = $("#ipv4").val();
            current_iface.listen_port = $("#port").val();
            current_iface.on_up = $("#onUp").val();
            current_iface.on_down = $("#onDown").val();
        }

        let autoStart = $('#autoStart .active').text().trim().toLowerCase() === "on";

        const autoStartGroup = $("#autoStart");
        autoStartGroup.click(function(e) {
            const status = $('#autoStart .active').text().trim().toLowerCase();
            autoStart = !(status === "on");
            current_iface.auto = autoStart;
        });

        $(".ifaceInputName").hover(function (e) {
            $(this).css("color", "#4e555b");
        }, function (e) {
            $(this).css("color", "black");
        });

        current_iface.auto = autoStart;


    }
}
