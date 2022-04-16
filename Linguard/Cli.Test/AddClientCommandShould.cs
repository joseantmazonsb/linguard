using System.Linq;
using System.Threading.Tasks;
using Bogus;
using Castle.Core.Internal;
using FluentAssertions;
using Linguard.Cli.Commands;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Moq;
using Typin.Attributes;
using Xunit;

namespace Cli.Test; 

public class AddClientCommandShould {
    
    private static readonly Mock<IWireguardService> WireguardServiceMock = new();

    [Fact]
    public async Task CreateRandomClient() {
        var command = typeof(AddClientCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var iface = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface);

        var commandLine = $"{commandName} --interface {iface.Name}";

        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        iface.Clients.Should().NotBeEmpty();
    }
    
    [Fact]
    public async Task CreateClientWithName() {
        var command = typeof(AddClientCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var iface = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface);

        const string name = "bob";
        var commandLine = $"{commandName} --interface {iface.Name} --name {name}";

        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        iface.Clients.Should().NotBeEmpty();
        iface.Clients.First().Name.Should().Be(name);
    }
    
    [Fact]
    public async Task CreateClientWithEndpoint() {
        var command = typeof(AddClientCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var iface = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface);

        const string endpoint = "vpn.example2.com";
        var commandLine = $"{commandName} --interface {iface.Name} --endpoint {endpoint}";

        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        iface.Clients.Should().NotBeEmpty();
        iface.Clients.First().Endpoint.ToString().Should().Be(endpoint);
    }
    
    [Fact]
    public async Task CreateClientWithIPs() {
        var command = typeof(AddClientCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var iface = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface);

        var faker = new Faker();
        var ipv4 = $"{faker.Internet.Ip()}/24";
        var ipv6 = $"{faker.Internet.Ipv6()}/64";
        var commandLine = $"{commandName} --interface {iface.Name} --ipv4 {ipv4} --ipv6 {ipv6}";

        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        iface.Clients.Should().NotBeEmpty();
        var client = iface.Clients.First();
        client.IPv6Address!.ToString().Should().Be(ipv6);
        client.IPv4Address!.ToString().Should().Be(ipv4);
    }
    
    [Fact]
    public async Task CreateClientWithDns() {
        var command = typeof(AddClientCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var iface = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface);

        var dns = "my.dns.com";
        var commandLine = $"{commandName} --interface {iface.Name} --dns1 {dns}";

        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        iface.Clients.Should().NotBeEmpty();
        var client = iface.Clients.First();
        client.PrimaryDns.ToString().Should().Be(dns);
        client.SecondaryDns.Should().NotBeNull();
    }
    
    [Fact]
    public async Task CreateClientWithTwoDns() {
        var command = typeof(AddClientCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var iface = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface);

        var dns1 = "my.dns.com";
        var dns2 = "8.8.8.8";
        var commandLine = $"{commandName} --interface {iface.Name} --dns1 {dns1} --dns2 {dns2}";

        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        iface.Clients.Should().NotBeEmpty();
        var client = iface.Clients.First();
        client.PrimaryDns.ToString().Should().Be(dns1);
        client.SecondaryDns!.ToString().Should().Be(dns2);
    }
    
    [Fact]
    public async Task CreateClientWithAllowedIPs() {
        var command = typeof(AddClientCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var iface = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface);

        const string allowedIPs = "10.7.1.2/24 10.7.1.3/24 10.8.1.3/24";
        var commandLine = $"{commandName} --interface {iface.Name} --allowedIps {allowedIPs}";

        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        iface.Clients.Should().NotBeEmpty();
        string.Join(" ", iface.Clients.First().AllowedIPs).Should().Be(allowedIPs);
    }

    private Interface GenerateInterface(IConfigurationManager configuration) {
        return new DefaultInterfaceGenerator(configuration, 
            WireguardServiceMock.Object, new SystemWrapper()).Generate();
    }
}