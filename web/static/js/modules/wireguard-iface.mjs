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

        function sendPost(url, onSuccess, onSuccessAlertType = AlertType.SUCCESS) {
            const data = {
                "name": $("#name").val(),
                "description": $("#description").val(),
                "gw": $("#gw").val(),
                "ipv4": $("#ipv4").val(),
                "port": $("#port").val(),
                "on_up": $("#onUp").val(),
                "on_down": $("#onDown").val()
            };
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
            sendPost(url, "Changes saved! Don't forget to <strong>apply</strong> them before leaving.",
                AlertType.WARN)
        });

        const applytIfaceBtn = $("#applyBtn");
        applytIfaceBtn.click(function (e) {
            const url = location.href+"/apply";
            sendPost(url, "Configuration <strong>applied</strong>!")
        });

        const regenerateKeysBtn = $("#regenerateKeysBtn");
        regenerateKeysBtn.click(function (e) {
            const url = location.href+"/regenerate-keys";
            sendPost(url, "Keys regenerated!");
        });

        const addIfaceBtn = $("#addBtn");
        addIfaceBtn.click(function (e) {
            const url = location.href.split("?")[0];
            const data = {
                "name": $("#name").val(),
                "description": $("#description").val(),
                "gw": $("#gw").val(),
                "ipv4": $("#ipv4").val(),
                "port": $("#port").val(),
                "on_up": $("#onUp").val(),
                "on_down": $("#onDown").val()
            };
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
                    prependAlert(alertContainer, "New interface added!", AlertType.SUCCESS, 1500, true, function () {
                        location.replace("..");
                    });
                },
                error: function(resp) {
                    prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"]);
                },
                complete: function (resp) {
                    loadFeeback.hide();
                },
            });
        });
    }
}
