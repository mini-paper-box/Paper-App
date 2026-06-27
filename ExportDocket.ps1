# Load AMO assembly from Power BI Desktop
Add-Type -Path "C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.AnalysisServices.Tabular.dll"

# Power BI Desktop server/port
$serverName = "localhost:50458"
$databaseName = "Model"

# Connect to running Power BI Desktop model
$server = New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect($serverName)
$database = $server.Databases[$databaseName]

# Load DAX query from file
$daxQueryFile = "C:\Users\sang.n\Desktop\DAX\order_query.txt"
$daxQuery = Get-Content $daxQueryFile -Raw

# Execute DAX query
$result = $database.ExecuteDax($daxQuery)

# Export result to CSV
$outputCSV = "C:\Users\sang.n\Desktop\DAX\order_export.csv"
$result | Export-Csv -Path $outputCSV -NoTypeInformation

# Disconnect
$server.Disconnect()
