using FluentValidation;
using Linguard.Core;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Services;
using Linguard.Log;
using Typin.Attributes;
using Typin.Console;

namespace Linguard.Cli.Commands; 

[Command("edit interface", Description = "Edit the configuration of an existent interface.")]
public class EditInterfaceCommand : AddInterfaceCommand {
    public EditInterfaceCommand(IConfigurationManager configurationManager, ILogger logger, 
        IInterfaceGenerator interfaceGenerator, AbstractValidator<Interface> validator) 
        : base(configurationManager, logger, interfaceGenerator, validator) {
    }

    public override ValueTask ExecuteAsync(IConsole console) {
        var iface = Configuration.Wireguard.Interfaces.SingleOrDefault(i => i.Name.Equals(Name));
        if (iface == default) {
            Logger.Error($"No interface named '{Name}' was found.");
            console.Error.WriteLine(Validation.InterfaceNotFound);
            return ValueTask.CompletedTask;
        }
        ApplyParametersSetByUser(iface);
        if (!Validate(iface, console)) {
            return ValueTask.CompletedTask;
        }
        ConfigurationManager.Save();
        return base.ExecuteAsync(console);
    }
}