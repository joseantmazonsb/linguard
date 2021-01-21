import {AlertType, postJSON, prependAlert} from "./utils.mjs";

export { WireguardIface }

class WireguardIface {

    static load() {

        const ifaceNameInput = $("#name");
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

        const resetIfaceBtn = $("#resetBtn");
        resetIfaceBtn.click(function (e) {
           location.reload();
        });

        const saveIfaceBtn = $("#saveBtn");
        saveIfaceBtn.click(function (e) {
            const url = location.href+"/save";
            const alertContainer = "wgIfaceConfig";
            const loadFeeback = $("#wgLoading");
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
                    prependAlert(alertContainer,
                        "Changes saved! Don't forget to <strong>apply</strong> them before leaving.",
                        AlertType.WARN, 7000, true);
                },
                error: function(resp) {
                    prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"]);
                },
                complete: function (resp) {
                    loadFeeback.hide();
                },
            });
        });

        const applytIfaceBtn = $("#applyBtn");
        applytIfaceBtn.click(function (e) {
        });
    }
}
