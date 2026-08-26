from fairvalue.storage import CsvRepository


def test_repository_crud_and_unique_insert(tmp_path):
    repo = CsvRepository(tmp_path)
    account = repo.add(
        "accounts",
        {
            "prop_firm": "Test Firm",
            "account_type": "Evaluation",
            "account_size": 50000,
            "status": "Eval",
        },
    )
    assert len(repo.list("accounts")) == 1
    repo.update("accounts", account["id"], {"status": "Funded"})
    assert repo.list("accounts").iloc[0]["status"] == "Funded"

    record = {
        "trade_key": "same-key",
        "source": "Test",
        "symbol": "NQ",
        "quantity": 1,
        "net_pnl": 100,
    }
    assert repo.add_many_unique("trades", [record], "trade_key") == (1, 0)
    assert repo.add_many_unique("trades", [record], "trade_key") == (0, 1)
    assert repo.delete("accounts", account["id"])

