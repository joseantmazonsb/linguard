import {AlertType, prependAlert} from "./utils.mjs";

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
    let value = onUp.val();
    value = value.replace(oldVal, newVal);
    onUp.val(value);

    value = onDown.val();
    // FIXME: this should only match the word but it doesn't and just fuck js.
    value = value.replace(new RegExp("^"+oldVal+"$"), newVal);
    //value = value.replace(oldVal, newVal);
    onDown.val(value);
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
        "auto": $('#autoStart .active').text().trim().toLowerCase() === "on"
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
        "auto": $('#autoStart .active').text().trim().toLowerCase() === "on"
    };
    sendPost(url,"Configuration <strong>applied</strong>!", AlertType.SUCCESS, data)
});

const refreshKeysBtn = $("#refreshKeysBtn");
refreshKeysBtn.click(function (e) {
    const url = location.href+"/regenerate-keys";
    sendPost(url, "Keys updated!");
});

const addIfaceBtn = $("#addBtn");
addIfaceBtn.click(function (e) {
    addIfaceBtn.attr("disabled", true);
    resetIfaceBtn.attr("disabled", true);
    const url = location.href+"/"+$("#uuid").text();
    const data = {
        "name": $("#name").val(),
        "description": $("#description").val(),
        "gw_iface": $("#gw").val(),
        "ipv4_address": $("#ipv4").val(),
        "listen_port": $("#port").val(),
        "on_up": $("#onUp").val(),
        "on_down": $("#onDown").val(),
        "auto": $('#autoStart .active').text().trim().toLowerCase() === "on"
    };
    $.ajax({
        type: "post",
        url: url,
        data: JSON.stringify({"data": data}), // Filled up in jinja template
        dataType: 'json',
        contentType: 'application/json',
        beforeSend : function () {
            loadFeeback.show();
        },
        success: function (resp) {
            prependAlert(alertContainer, "New interface added!", AlertType.SUCCESS, 1500, true, function () {
                location.replace(document.referrer);
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

$(".ifaceInputName").hover(function (e) {
    $(this).css("color", "#4e555b");
}, function (e) {
    $(this).css("color", "black");
});
