using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;

namespace WebMock; 

public class ApplicationDbContextMock : IdentityDbContext {
    
    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder) {
        base.OnConfiguring(optionsBuilder);
        var connectionString = new SqliteConnectionStringBuilder {
            DataSource = "mock.db",
            Cache = SqliteCacheMode.Shared
        }.ConnectionString;
        optionsBuilder.UseSqlite(connectionString);
    }
}