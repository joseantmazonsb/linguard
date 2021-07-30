import {AlertType, prependAlert} from "./utils.mjs";

const loadFeeback = $("#wgLoading");
const alertContainer = "alertContainer";

const saveBtn = $("#saveBtn");
saveBtn.click(function (e) {
    const url = location.href+"/save";
    const data = {
        "logger": {
            "logfile": $("#logfile").val(),
            "level": $("#loglevel").val(),
            "overwrite": $('#overwrite .active').text().trim().toLowerCase() === "yes"
        },
        "web": {
            "bindport": $("#port").val(),
            "login_attempts": $("#loginAttempts").val(),
        },
        "linguard": {
            "endpoint": $("#endpoint").val(),
            "wg_bin": $("#wgBin").val(),
            "wg_quick_bin": $("#wgQuickBin").val(),
            "iptables_bin": $("#iptablesBin").val(),
            "interfaces_folder": $("#interfacesDir").val(),
        }
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
            prependAlert(alertContainer, "Settings saved! Have in mind that you may need to restart the app to " +
                "apply some changes.", AlertType.SUCCESS,
                5000, true);
        },
        error: function(resp) {
            prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"]);
        },
        complete: function (resp) {
            loadFeeback.hide();
        },
    });
});