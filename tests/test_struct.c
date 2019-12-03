struct other_struct {
    int some_field;
};

struct test_struct {
    int first_field;
    char second_field;
    unsigned long *third_field;
    float last_field;

    char my_array[17];

    // pointers to pointers are broken
    // void **p;

    // other structs are a bit broken
    // struct other_struct z;
};
