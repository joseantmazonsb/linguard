import {AlertType, prependAlert} from "./utils.mjs";

const addPeerBtn = $("#addPeerBtn");
const loadFeeback = $("#wgLoading");
const alertContainer = "wgPeerConfig";
const resetBtn = $("#resetBtn");


$(".peerInputName").hover(function (e) {
    $(this).css("color", "#4e555b");
}, function (e) {
    $(this).css("color", "black");
});

resetBtn.click(function (e) {
   location.reload();
});

addPeerBtn.click(function (e) {
    addPeerBtn.attr("disabled", true);
    resetBtn.attr("disabled", true);
    const url = location.href;
    const data = {
        "name": $("#name").val(),
        "description": $("#description").val(),
        "interface": $("#interface").val(),
        "ipv4_address": $("#ipv4").val(),
        "dns1": $("#dns1").val(),
        "dns2": $("#dns2").val(),
        "nat": $('#nat .active').text().trim().toLowerCase() === "yes"
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
            prependAlert(alertContainer, "New peer added!", AlertType.SUCCESS, 1500, true, function () {
                location.replace(document.referrer);
            });
        },
        error: function(resp) {
            prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"]);
            addPeerBtn.attr("disabled", false);
            resetBtn.attr("disabled", false);
        },
        complete: function (resp) {
            loadFeeback.hide();
        },
    });
});

const saveBtn = $("#saveBtn");
saveBtn.click(function (e) {
    const url = location.href+"/save";
    const data = {
        "name": $("#name").val(),
        "description": $("#description").val(),
        "interface": $("#interface").val(),
        "ipv4_address": $("#ipv4").val(),
        "dns1": $("#dns1").val(),
        "dns2": $("#dns2").val(),
        "nat": $('#nat .active').text().trim().toLowerCase() === "yes"
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
            prependAlert(alertContainer, "Changes saved! You may now download the updated configuration.", AlertType.SUCCESS,
                3000, true);
        },
        error: function(resp) {
            prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"]);
        },
        complete: function (resp) {
            loadFeeback.hide();
        },
    });
});

const removePeerBtn = $(".removeBtn");
removePeerBtn.click(function (e) {
    const item = e.target.id.split("-")[1];
    const url = "/wireguard/peers/"+item+"/remove";
    const alertContainer = "wgPeerConfig";
    const alertType = "danger";
    $.ajax({
        type: "delete",
        url: url,
        success: function () {
            location.replace(document.referrer);
        },
        error: function(resp) {
            prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"],
                alertType);
            $("#removeModal").modal("toggle");
        },
    });
});

const downloadBtn = $(".downloadBtn");
downloadBtn.click(function (e) {
    const item = e.target.id.split("-")[1];
    const url = "/wireguard/peers/"+item+"/download";
    location.replace(url);
});