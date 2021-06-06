import {postJSON, prependAlert} from "./utils.mjs";

const startOrStopIfaceBtn = $(".startOrStopIfaceBtn");
startOrStopIfaceBtn.click(function (e) {
    const button = e.target;
    const iface = button.value;
    const action = button.innerText;

    const url = "/wireguard/interfaces/" + iface;
    const data = JSON.stringify({"action": action})
    const alertContainer = "wgIfacesHeader";
    const alertType = "danger";
    const loadFeedback = "wgIface-" + iface + "-loading"

    postJSON(url, alertContainer, alertType, loadFeedback, data);
});

const restartIfaceBtn = $(".restartIfaceBtn");
restartIfaceBtn.click(function (e) {
    const iface = e.target.value;
    const action = "restart";

    const url = "/wireguard/interfaces/" + iface;
    const data = JSON.stringify({"action": action})
    const alertContainer = "wgIfacesHeader";
    const alertType = "danger";
    const loadFeedback = "wgIface-" + iface + "-loading"

    postJSON(url, alertContainer, alertType, loadFeedback, data);
});

const removeIfaceBtn = $(".removeIfaceBtn");
removeItem(removeIfaceBtn, "interface");

const removePeerBtn = $(".removePeerBtn");
removeItem(removePeerBtn, "peer");

function removeItem(removeBtn, itemType) {
    removeBtn.click(function (e) {
        const item = e.target.id.split("-")[1];
        const url = "/wireguard/"+itemType+"s/"+item+"/remove";
        const alertContainer = "wgIfacesHeader";
        const alertType = "danger";
        $.ajax({
            type: "delete",
            url: url,
            success: function () {
                location.reload();
            },
            error: function(resp) {
                prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"],
                    alertType);
                $("#removeModal").modal("toggle");
            },
        });
    });
}

const downloadBtn = $(".downloadBtn");
downloadBtn.click(function (e) {
    let item = e.target.id.split("-")[1];
    if (!item) {
        item = e.target.farthestViewportElement.id.split("-")[1];
    }
    const url = "/wireguard/peers/"+item+"/download";
    location.replace(url);
});