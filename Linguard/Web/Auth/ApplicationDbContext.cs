using Linguard.Core.Managers;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;

namespace Linguard.Web.Auth; 

public class ApplicationDbContext : IdentityDbContext {
    private readonly IConfigurationManager _configurationManager;
    
    public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options, IConfigurationManager configurationManager)
        : base(options) {
        _configurationManager = configurationManager;
    }

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder) {
        base.OnConfiguring(optionsBuilder);
        var connectionString = new SqliteConnectionStringBuilder {
            DataSource = _configurationManager.WorkingDirectory.CredentialsPath,
            Cache = SqliteCacheMode.Shared
        }.ConnectionString;
        optionsBuilder.UseSqlite(connectionString);
    }
}