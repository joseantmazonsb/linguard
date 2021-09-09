import {prependAlert} from "./utils.mjs";

const removeIfaceBtn = $(".removeIfaceBtn");
removeItem(removeIfaceBtn, "interface");

const removePeerBtn = $(".removePeerBtn");
removeItem(removePeerBtn, "peer");

function removeItem(removeBtn, itemType) {
    removeBtn.click(function (e) {
        const item = e.target.id.split("-")[1];
        const url = "/wireguard/"+itemType+"s/"+item+"";
        const alertContainer = "global_alerts";
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