from stride.db_interface import make_stride_table_name, make_dsgrid_data_table_name


def test_make_stride_table_name() -> None:
    assert make_stride_table_name("baseline", "gdp") == "stride.baseline__gdp"


def test_make_dsgrid_data_table_name() -> None:
    assert (
        make_dsgrid_data_table_name("baseline", "gdp", version="2.0.0")
        == "dsgrid_data.baseline__gdp__2_0_0"
    )
