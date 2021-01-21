export { WireguardIface }

class WireguardIface {

    static load() {
        const ifaceNameInput = $("#ifaceName");
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
    }
}
