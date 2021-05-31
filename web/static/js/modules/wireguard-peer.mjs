import {AlertType, prependAlert} from "./utils.mjs";

const addPeerBtn = $("#addPeerBtn");
const loadFeeback = $("#wgLoading");
const alertContainer = "wgPeerConfig";
const resetBtn = $("#resetBtn");
const natGroup = $("#nat");

let nat = $('#nat .active').text().trim().toLowerCase() === "yes";

natGroup.click(function(e) {
    const status = $('#nat .active').text().trim().toLowerCase();
    nat = !(status === "yes");
});

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
        "nat": nat
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
                const url = location.href.substring(0, location.href.lastIndexOf("/"));
                location.replace(url);
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